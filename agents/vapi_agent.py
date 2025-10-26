"""
Vapi Agent - Handles AI phone call negotiations with listing agents
"""

from datetime import datetime
from uuid import uuid4
from uagents import Agent, Context, Protocol, Model
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)
from typing import Optional, Dict, Any, List
import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

# Import VapiClient after ensuring dotenv is loaded
try:
    from vapi_client import VapiClient
except ImportError:
    print("⚠️ WARNING: vapi_client module not found")
    VapiClient = None


# Vapi Models for uAgents
class VapiRequest(Model):
    """Request to make a negotiation call via Vapi"""
    property_address: str
    user_name: str
    user_email: str
    user_preferences: str
    intelligence: Dict[str, Any]  # The full intelligence JSON from prober
    session_id: str


class VapiResponse(Model):
    """Response from Vapi agent"""
    call_id: Optional[str] = None
    status: str
    message: str
    session_id: str
    call_summary: Optional[str] = None


def build_system_prompt(vapi_context: Dict[str, Any]) -> str:
    """Build the system prompt for Vapi assistant with intelligence data"""

    property_addr = vapi_context['property']['address']
    user_name = vapi_context['user']['name']
    user_prefs = vapi_context['user']['preferences']
    leverage_score = vapi_context['intelligence']['leverage_score']
    assessment = vapi_context['intelligence']['overall_assessment']
    findings = vapi_context['intelligence']['findings']

    # Format findings for the prompt
    findings_text = ""
    for idx, finding in enumerate(findings, 1):
        findings_text += f"""
{idx}. {finding['category'].upper().replace('_', ' ')} (Leverage Score: {finding['leverage_score']}/10)
   - Summary: {finding['summary']}
   - Details: {finding['details']}
"""
        if finding.get('source_url'):
            findings_text += f"   - Source: {finding['source_url']}\n"

    system_prompt = f"""You are an AI negotiation agent representing the buyer {user_name} for the property at {property_addr}.

You are on a PHONE CALL with the listing agent to negotiate a better price. Your goal is to use the intelligence data below to get the LOWEST possible price for your client.

====================
BUYER INFORMATION
====================
Name: {user_name}
Preferences: {user_prefs}

====================
PROPERTY INTELLIGENCE
====================
Overall Leverage Score: {leverage_score}/10 (higher = more buyer leverage)

Overall Assessment:
{assessment}

Key Findings (USE THESE AS LEVERAGE):
{findings_text}

====================
NEGOTIATION STRATEGY
====================

1. OPENING:
   - Identify yourself as representing {user_name}
   - Express serious interest in the property
   - Mention you've done thorough market research

2. PRESENT CONCERNS (use the findings above):
   - Reference specific data points from findings
   - Focus on HIGH leverage score items first (8+ scores)
   - Be specific with numbers (days on market, price reductions, etc.)
   - Frame as "market analysis" not criticism

3. REQUEST PRICE REDUCTION:
   - Based on the leverage score and findings, suggest a price adjustment
   - If leverage score is 7-10: Request 5-10% reduction
   - If leverage score is 5-7: Request 3-5% reduction
   - If leverage score is 3-5: Request 1-3% reduction
   - Justify with specific findings

4. HANDLE OBJECTIONS:
   - If they dispute findings, ask for their counter-data
   - Emphasize your client's serious interest and ability to close
   - Reference buyer's preferences: {user_prefs}
   - Stay professional but persistent

5. CLOSING:
   - Try to get verbal agreement on adjusted price
   - Offer to submit formal offer immediately
   - Get next steps (inspection, paperwork, etc.)

====================
RULES (MUST FOLLOW)
====================
- Keep responses BRIEF (under 75 words per turn)
- Be conversational and natural (you're on a phone call)
- Use ONLY the intelligence data provided - do NOT fabricate facts
- Stay professional and respectful
- Focus on DATA and MARKET CONDITIONS, not personal attacks
- Follow Fair Housing laws - no discriminatory language
- Do NOT use emojis or special formatting

====================
EXAMPLE OPENING
====================
"Hi, this is calling on behalf of {user_name} regarding the property at {property_addr}. We're very interested, but our market analysis has identified some concerns we'd like to discuss. Do you have a moment to talk about the pricing?"

====================
KEY TALKING POINTS
====================
Based on your intelligence, emphasize:
{chr(10).join([f"- {f['summary']}" for f in findings[:3]])}

Remember: Your job is to get the LOWEST price possible while being professional. Use the intelligence data strategically!
"""

    return system_prompt.strip()


def extract_phone_number(text: str) -> Optional[str]:
    """Extract phone number from text. Supports various formats."""
    # Patterns for phone numbers
    patterns = [
        r'\+?1?\s*\(?(\d{3})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})',  # US format
        r'\+(\d{1,3})\s*\(?(\d{1,4})\)?[\s.-]?(\d{3,4})[\s.-]?(\d{4})',  # International
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            # Clean up and format the number
            digits = ''.join(re.findall(r'\d', match.group(0)))
            if len(digits) == 10:
                return f"+1{digits}"
            elif len(digits) == 11 and digits[0] == '1':
                return f"+{digits}"
            elif digits.startswith('+'):
                return digits
            else:
                return f"+{digits}"

    return None

# Initialize Vapi client
try:
    vapi_client = VapiClient() if VapiClient else None
except Exception as e:
    print(f"⚠️ WARNING: Failed to initialize Vapi client: {e}")
    vapi_client = None

# Create the agent (following boilerplate pattern)
agent = Agent(
    name="vapi-negotiator",
    seed="vapi_agent_seed_12345",
    mailbox=True,
)

# Create protocol compatible with chat protocol spec
protocol = Protocol(spec=chat_protocol_spec)


# Handler for chat messages from agentverse
@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    # Send acknowledgement for receiving the message
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(), acknowledged_msg_id=msg.msg_id),
    )

    # Collect all text chunks from the chat message
    text = ''
    for item in msg.content:
        if isinstance(item, TextContent):
            text += item.text

    ctx.logger.info(f"📞 Received message: {text[:100]}...")

    # Check if there's a phone number in the message
    phone_number = extract_phone_number(text)

    if not phone_number:
        # No phone number found - ask for it
        response = "Hi! I'm your AI negotiation agent. I can make phone calls to negotiate on your behalf.\n\nTo get started, please provide the phone number you'd like me to call.\n\nYou can send it in any format like:\n- (555) 123-4567\n- 555-123-4567\n- +1 555 123 4567"

        # Don't end session - wait for phone number
        await ctx.send(sender, ChatMessage(
            timestamp=datetime.utcnow(),
            msg_id=uuid4(),
            content=[
                TextContent(type="text", text=response),
            ]
        ))
        return

    # Phone number found - proceed with the call
    ctx.logger.info(f"📞 Phone number extracted: {phone_number}")

    response = 'I am afraid something went wrong and I am unable to make the call at the moment'

    try:
        if not vapi_client:
            response = "❌ Vapi client not initialized (missing API key)"
        else:
            # Simple system prompt for general conversation
            system_prompt = f"""You are a friendly AI assistant making a phone call on behalf of a user.

The user's message was: "{text}"

Your job is to have a natural, helpful conversation based on what the user asked you to discuss.

RULES:
- Keep responses BRIEF (under 75 words per turn)
- Be conversational and natural (you're on a phone call)
- Stay professional and respectful
- Do NOT use emojis or special formatting
- Listen carefully and respond appropriately to what the other person says

Start the call by introducing yourself and explaining why you're calling based on the user's request.
"""

            # Simple first message
            first_message = "Hi, this is an AI assistant calling on behalf of a user. Do you have a moment to chat?"

            # Update Vapi assistant
            ctx.logger.info(f"📝 Updating Vapi assistant...")
            success = vapi_client.update_assistant(
                system_prompt=system_prompt,
                first_message=first_message
            )

            if not success:
                raise Exception("Failed to update Vapi assistant")

            ctx.logger.info("✅ Assistant updated successfully")

            # Make the phone call
            ctx.logger.info(f"📞 Initiating call to {phone_number}...")
            call_id = vapi_client.create_call(customer_phone=phone_number)

            if not call_id:
                raise Exception("Failed to create call")

            ctx.logger.info(f"✅ Call initiated! Call ID: {call_id}")

            # Wait for call to complete and get analysis summary
            ctx.logger.info("⏳ Waiting for call to complete and analysis to be generated...")
            call_summary = vapi_client.wait_for_call_analysis(call_id, timeout_seconds=120)

            if call_summary:
                ctx.logger.info(f"✅ Got call summary: {call_summary[:100]}...")
                response = f"✅ Call completed to {phone_number}!\n\nCall ID: {call_id}\n\nSummary:\n{call_summary}"
            else:
                ctx.logger.warning("⚠️ Call analysis not available (timeout or error)")
                response = f"✅ Call completed to {phone_number}! Call ID: {call_id}\n\nCall analysis not yet available (timeout or processing)."

    except Exception as e:
        ctx.logger.exception(f'Error processing Vapi call: {e}')
        response = f"❌ Failed to initiate call: {str(e)}"

    # Send the response back to the sender and end session
    await ctx.send(sender, ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=[
            # Send the response back
            TextContent(type="text", text=response),
            # Signal that the session is over
            EndSessionContent(type="end-session"),
        ]
    ))


@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    # Not processing acknowledgements in this example, but they can be useful
    # for implementing read receipts
    pass


# Attach the protocol to the agent
agent.include(protocol, publish_manifest=True)


if __name__ == "__main__":
    agent.run()
