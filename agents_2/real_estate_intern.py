"""
General Agent - Handles general questions about areas, neighborhoods, etc.
"""
from datetime import datetime
from uuid import uuid4

from openai import OpenAI
from uagents import Context, Protocol, Agent
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

try:
    from .tavily_client import TavilyClient
except ImportError:
    from tavily_client import TavilyClient


def create_text_chat(text: str, end_session: bool = False) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(timestamp=datetime.utcnow(), msg_id=uuid4(), content=content)


# OpenAI client for ASI-1
client = OpenAI(
    # By default, we are using the ASI-1 LLM endpoint and model
    base_url='https://api.asi1.ai/v1',

    # You can get an ASI-1 api key by creating an account at https://asi1.ai/dashboard/api-keys
    api_key='sk_80bae86f09db46f69cc178374c48f0766d57bd72a8164c728f52625c9105ec55',
)

# Tavily client for search
tavily = TavilyClient()

agent = Agent(
    name="Real Estate Intern",
    seed="general_agent_seed_12345",
    mailbox=True,
)

# We create a new protocol which is compatible with the chat protocol spec. This ensures
# compatibility between agents
protocol = Protocol(spec=chat_protocol_spec)


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

    try:
        ctx.logger.info(f"Received question: {text}")

        # Perform Tavily search for general information
        search_query = f"{text} Bay Area"

        ctx.logger.info(f"Searching with query: {search_query}")

        search_results = await tavily.search(
            query=search_query,
            search_depth="advanced",
            max_results=10
        )

        if not search_results["success"]:
            ctx.logger.error(f"Tavily search failed: {search_results['error']}")
            response = f"I'm having trouble searching for that information right now. Error: {search_results['error']}"
            await ctx.send(sender, create_text_chat(response, end_session=True))
            return

        # Build context for LLM from search results
        context = f"User Question: {text}\n\n"
        context += "Search Results:\n\n"

        for idx, result in enumerate(search_results["results"][:5], 1):
            context += f"Result {idx}:\n"
            context += f"Title: {result.get('title', 'N/A')}\n"
            context += f"URL: {result.get('url', 'N/A')}\n"
            context += f"Content: {result.get('content', 'N/A')[:800]}...\n\n"

        # Query the LLM
        r = client.chat.completions.create(
            model="asi1-mini",
            messages=[
                {"role": "system", "content": """You are a knowledgeable Bay Area real estate assistant who answers general questions about neighborhoods, areas, schools, amenities, and local information.

Your job is to provide helpful, accurate information based on search results.

CRITICAL RULES:
- Answer questions conversationally and naturally
- Use the search results to provide accurate information
- If search results don't contain the answer, say so honestly
- Focus on information relevant to someone looking for a home
- Be concise but informative"""},
                {"role": "user", "content": f"{context}\n\nBased on the search results above, answer the user's question: \"{text}\"\n\nProvide a clear, helpful answer. If the search results don't contain enough information to answer the question, say so honestly."},
            ],
            max_tokens=800,
            temperature=0.3,
        )

        response = str(r.choices[0].message.content)
        ctx.logger.info("Generated answer for general question")

    except Exception as e:
        ctx.logger.exception('Error processing request')
        response = f"An error occurred while processing the request. Please try again later. {e}"

    await ctx.send(sender, create_text_chat(response, end_session=True))


@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    # we are not interested in the acknowledgements for this example, but they can be useful to
    # implement read receipts, for example.
    pass


# attach the protocol to the agent
agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
