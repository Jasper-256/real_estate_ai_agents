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


# Target phone number for listing agent
TARGET_PHONE_NUMBER = "" # Add phone number here

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

    ctx.logger.info(f"📞 Received chat message: {text[:100]}...")

    # Parse the incoming message as JSON containing negotiation request
    response = 'I am afraid something went wrong and I am unable to process your negotiation request at the moment'

    try:
        # Expect JSON format from prober agent
        request_data = json.loads(text)

        property_address = request_data.get('property_address', 'Unknown')
        user_name = request_data.get('user_name', 'Client')
        user_email = request_data.get('user_email', '')
        user_preferences = request_data.get('user_preferences', '')
        intelligence = request_data.get('intelligence', {})

        ctx.logger.info(f"📞 Vapi call request for: {property_address}")
        ctx.logger.info(f"   User: {user_name}")
        ctx.logger.info(f"   Leverage Score: {intelligence.get('leverage_score', 0)}/10")

        if not vapi_client:
            response = "❌ Vapi client not initialized (missing API key)"
        else:
            # Build full context for system prompt
            vapi_context = {
                "property": {
                    "address": property_address
                },
                "user": {
                    "name": user_name,
                    "email": user_email,
                    "preferences": user_preferences
                },
                "intelligence": intelligence
            }

            # Build system prompt with all intelligence
            ctx.logger.info("🔧 Building system prompt with intelligence data...")
            system_prompt = build_system_prompt(vapi_context)

            # Build first message
            first_message = f"Hi, I'm calling on behalf of {user_name} regarding the property at {property_address}. We're very interested and have done some market research. Do you have a moment to discuss?"

            # Update Vapi assistant with new system prompt
            ctx.logger.info(f"📝 Updating Vapi assistant...")
            success = vapi_client.update_assistant(
                system_prompt=system_prompt,
                first_message=first_message
            )

            if not success:
                raise Exception("Failed to update Vapi assistant")

            ctx.logger.info("✅ Assistant updated successfully")

            # Make the phone call
            ctx.logger.info(f"📞 Initiating call to {TARGET_PHONE_NUMBER}...")
            call_id = vapi_client.create_call(customer_phone=TARGET_PHONE_NUMBER)

            if not call_id:
                raise Exception("Failed to create call")

            ctx.logger.info(f"✅ Call initiated! Call ID: {call_id}")

            # Wait for call to complete and get analysis summary
            ctx.logger.info("⏳ Waiting for call to complete and analysis to be generated...")
            call_summary = vapi_client.wait_for_call_analysis(call_id, timeout_seconds=120)

            if call_summary:
                ctx.logger.info(f"✅ Got call summary: {call_summary[:100]}...")
                response = f"✅ Call completed!\n\nCall ID: {call_id}\n\nSummary:\n{call_summary}"
            else:
                ctx.logger.warning("⚠️ Call analysis not available (timeout or error)")
                response = f"✅ Call completed! Call ID: {call_id}\n\nCall analysis not yet available (timeout or processing)."

    except json.JSONDecodeError:
        ctx.logger.exception('Error parsing JSON request')
        response = "❌ Invalid request format. Expected JSON with property_address, user_name, user_preferences, and intelligence fields."
    except Exception as e:
        ctx.logger.exception(f'Error processing Vapi call: {e}')
        response = f"❌ Failed to initiate call: {str(e)}"

    # Send the response back to the sender
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
