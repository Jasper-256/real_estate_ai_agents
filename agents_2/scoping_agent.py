"""
Scoping Agent - Collects user requirements for property search
"""
from datetime import datetime
from uuid import uuid4

from uagents import Context, Protocol, Agent
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)
from llm_client import SimpleLLMAgent


def create_text_chat(text: str, end_session: bool = False) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(timestamp=datetime.utcnow(), msg_id=uuid4(), content=content)


# LLM client for conversation
llm_client = SimpleLLMAgent(
    "scoping_agent",
    system_prompt="""You are a friendly real estate agent helping users find their dream home in the San Francisco Bay Area.

Your job is to gather the following information from the user through natural conversation:
1. Budget (minimum and maximum price range)
2. Number of bedrooms
3. Number of bathrooms
4. Specific location within Bay Area (cities like San Francisco, Oakland, San Jose, etc.)

CRITICAL RULES:
- Be conversational and friendly
- Ask follow-up questions ONLY if you still need information
- Once you have ALL required information (budget, bedrooms, bathrooms, and location), mark as complete
- When marking as complete, ONLY provide a confirmation statement. NEVER ask any questions.
- If the user asks a follow-up question (like "do you have links?"), respond conversationally but mark as NOT complete
- Only mark as complete when starting a NEW property search

RESPONSE FORMATS:

1. If the user is asking a GENERAL QUESTION (about neighborhoods, schools, crime, amenities, etc.), respond with:
{
  "agent_message": "I'll look that up for you.",
  "is_complete": false,
  "is_general_question": true,
  "general_question": "<the user's question>"
}

2. If you have gathered ALL property search requirements (budget, bedrooms, bathrooms, location), respond with:
{
  "agent_message": "<simple confirmation without any questions>",
  "is_complete": true,
  "is_general_question": false,
  "requirements": {
    "budget_min": <number or null>,
    "budget_max": <number>,
    "bedrooms": <number>,
    "bathrooms": <number>,
    "location": "<city/area in Bay Area>",
    "additional_info": "<optional additional preferences or null>"
  }
}

3. If you need more information for a property search, respond with:
{
  "agent_message": "<your question or response>",
  "is_complete": false,
  "is_general_question": false
}"""
)

agent = Agent(
    name="Scoping Agent",
    seed="scoping_agent_seed_12343247",
    mailbox=True,
)

# We create a new protocol which is compatible with the chat protocol spec. This ensures
# compatibility between agents
protocol = Protocol(spec=chat_protocol_spec)

# Store conversation history per sender
conversations = {}


# We define the handler for the chat messages that are sent to your agent
@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    # send the acknowledgement for receiving the message
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(), acknowledged_msg_id=msg.msg_id),
    )

    text = msg.text()
    if not text:
        return

    # Initialize conversation history if not exists
    if sender not in conversations:
        conversations[sender] = []

    # Add user message to history
    conversations[sender].append({
        "role": "user",
        "content": text
    })

    # Build conversation context
    conversation_text = "\n".join([
        f"{'User' if m['role'] == 'user' else 'Agent'}: {m['content']}"
        for m in conversations[sender]
    ])

    prompt = f"""Based on the following conversation, determine the user's intent:

Conversation:
{conversation_text}

Determine if this is:
1. A GENERAL QUESTION (asking about neighborhoods, schools, crime, amenities, local info, etc.) → set "is_general_question: true"
2. A PROPERTY SEARCH REQUEST with all requirements (budget, bedrooms, bathrooms, location) → set "is_complete: true"
3. An INCOMPLETE property search or follow-up → set "is_complete: false" and "is_general_question: false"

Examples:
- "What's the crime rate in Castro District?" → general question
- "Tell me about schools in San Francisco" → general question
- "Find me a 2 bed 2 bath home in SF under 1.5M" → complete property search
- "I'm looking for a home" → incomplete (need more info)

Respond with a JSON object as specified in your instructions."""

    try:
        # Query LLM
        result = await llm_client.query_llm(prompt, temperature=0.3)

        if result["success"]:
            parsed = llm_client.parse_json_response(result["content"])

            if parsed:
                # DEBUG: Log the full parsed response
                ctx.logger.info(f"DEBUG - Parsed LLM response: {parsed}")
                ctx.logger.info(f"DEBUG - is_general_question: {parsed.get('is_general_question', False)}")
                ctx.logger.info(f"DEBUG - is_complete: {parsed.get('is_complete', False)}")

                agent_message = parsed.get("agent_message", "How can I help you find a home?")

                # Store agent response in history
                conversations[sender].append({
                    "role": "assistant",
                    "content": agent_message
                })

                # Log if requirements are gathered
                if parsed.get("is_complete", False) and "requirements" in parsed:
                    requirements = parsed["requirements"]
                    ctx.logger.info(f"Requirements gathered from {sender}: {requirements}")

                # Send response
                await ctx.send(sender, create_text_chat(agent_message, end_session=False))
            else:
                ctx.logger.warning("Failed to parse LLM response")
                response_msg = "I'm here to help you find a home in the Bay Area. What are you looking for?"
                conversations[sender].append({
                    "role": "assistant",
                    "content": response_msg
                })
                await ctx.send(sender, create_text_chat(response_msg, end_session=False))
        else:
            ctx.logger.error(f"LLM error: {result['content']}")
            response_msg = "I'm having trouble processing your request. Could you try again?"
            conversations[sender].append({
                "role": "assistant",
                "content": response_msg
            })
            await ctx.send(sender, create_text_chat(response_msg, end_session=False))

    except Exception as e:
        ctx.logger.exception('Error processing message')
        response_msg = f"An error occurred while processing your request. Please try again later."
        await ctx.send(sender, create_text_chat(response_msg, end_session=False))


@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    # we are not interested in the acknowledgements for this example, but they can be useful to
    # implement read receipts, for example.
    pass


# attach the protocol to the agent
agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
