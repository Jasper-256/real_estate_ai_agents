"""
Scoping Agent - Collects user requirements for property search
"""
from uagents import Agent, Context
from .models import ScopingRequest, ScopingResponse, UserRequirements
from .llm_client import SimpleLLMAgent


def create_scoping_agent(port: int = 8001):
    """Create and configure the scoping agent"""

    agent = Agent(
        name="scoping_agent",
        port=port,
        seed="scoping_agent_seed",
        endpoint=[f"http://localhost:{port}/submit"]
    )

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

    # Store conversation history per session
    conversations = {}

    @agent.on_event("startup")
    async def startup(ctx: Context):
        ctx.logger.info(f"Scoping Agent started at {ctx.agent.address}")

    @agent.on_message(model=ScopingRequest)
    async def handle_request(ctx: Context, sender: str, msg: ScopingRequest):
        ctx.logger.info(f"Scoping agent received message from {sender}")

        # Initialize conversation history
        if msg.session_id not in conversations:
            conversations[msg.session_id] = []

        # Add user message to history
        conversations[msg.session_id].append({
            "role": "user",
            "content": msg.user_message
        })

        # Build conversation context
        conversation_text = "\n".join([
            f"{'User' if m['role'] == 'user' else 'Agent'}: {m['content']}"
            for m in conversations[msg.session_id]
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

        # Query LLM
        result = await llm_client.query_llm(prompt, temperature=0.3)

        if result["success"]:
            parsed = llm_client.parse_json_response(result["content"])

            if parsed:
                # DEBUG: Log the full parsed response
                ctx.logger.info(f"DEBUG - Parsed LLM response: {parsed}")
                ctx.logger.info(f"DEBUG - is_general_question: {parsed.get('is_general_question', False)}")
                ctx.logger.info(f"DEBUG - is_complete: {parsed.get('is_complete', False)}")

                # Store agent response in history
                conversations[msg.session_id].append({
                    "role": "assistant",
                    "content": parsed.get("agent_message", "")
                })

                # Build response
                requirements = None
                community_name = None
                if parsed.get("is_complete", False) and "requirements" in parsed:
                    requirements = UserRequirements(**parsed["requirements"])
                    # Extract community name from location
                    community_name = requirements.location if requirements else None
                    ctx.logger.info(f"Requirements gathered for session {msg.session_id}, community: {community_name}")

                response = ScopingResponse(
                    agent_message=parsed.get("agent_message", "How can I help you find a home?"),
                    is_complete=parsed.get("is_complete", False),
                    session_id=msg.session_id,
                    requirements=requirements,
                    is_general_question=parsed.get("is_general_question", False),
                    general_question=parsed.get("general_question", None),
                    community_name=community_name
                )
            else:
                ctx.logger.warning("Failed to parse LLM response")
                response = ScopingResponse(
                    agent_message="I'm here to help you find a home in the Bay Area. What are you looking for?",
                    is_complete=False,
                    session_id=msg.session_id,
                    requirements=None
                )

            await ctx.send(sender, response)
        else:
            ctx.logger.error(f"LLM error: {result['content']}")
            response = ScopingResponse(
                agent_message="I'm having trouble processing your request. Could you try again?",
                is_complete=False,
                session_id=msg.session_id,
                requirements=None
            )
            await ctx.send(sender, response)

    return agent
