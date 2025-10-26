"""
General Agent - Handles general questions about areas, neighborhoods, etc.
"""
from uagents import Agent, Context
from .models import GeneralRequest, GeneralResponse
from .llm_client import SimpleLLMAgent
from .tavily_client import TavilyClient


def create_general_agent(port: int = 8003):
    """Create and configure the general agent"""

    agent = Agent(
        name="general_agent",
        port=port,
        seed="general_agent_seed",
        endpoint=[f"http://localhost:{port}/submit"]
    )

    # LLM client for answering questions
    llm_client = SimpleLLMAgent(
        "general_agent",
        system_prompt="""You are a knowledgeable Bay Area real estate assistant who answers general questions about neighborhoods, areas, schools, amenities, and local information.

Your job is to provide helpful, accurate information based on search results.

CRITICAL RULES:
- Answer questions conversationally and naturally
- Use the search results to provide accurate information
- If search results don't contain the answer, say so honestly
- Focus on information relevant to someone looking for a home
- Be concise but informative

Respond with a JSON object in this format:
{
  "answer": "<your detailed answer to the user's question>"
}"""
    )

    # Tavily client
    tavily = TavilyClient()

    @agent.on_event("startup")
    async def startup(ctx: Context):
        ctx.logger.info(f"General Agent started at {ctx.agent.address}")

    @agent.on_message(model=GeneralRequest)
    async def handle_request(ctx: Context, sender: str, msg: GeneralRequest):
        ctx.logger.info(f"General agent received question from {sender}: {msg.question}")

        # Perform Tavily search for general information
        search_query = f"{msg.question}"

        ctx.logger.info(f"Search query: {search_query}")

        search_results = await tavily.search(
            query=search_query,
            search_depth="advanced",
            max_results=10
        )

        if not search_results["success"]:
            ctx.logger.error(f"Tavily search failed: {search_results['error']}")
            response = GeneralResponse(
                answer=f"I'm having trouble searching for that information right now. Error: {search_results['error']}",
                session_id=msg.session_id
            )
            await ctx.send(sender, response)
            return
    
        # Build context for LLM from search results
        context = f"User Question: {msg.question}\n\n"
        context += "Search Results:\n\n"

        for idx, result in enumerate(search_results["results"][:5], 1):
            context += f"Result {idx}:\n"
            context += f"Title: {result.get('title', 'N/A')}\n"
            context += f"URL: {result.get('url', 'N/A')}\n"
            context += f"Content: {result.get('content', 'N/A')[:800]}...\n\n"

        prompt = f"""{context}

Based on the search results above, answer the user's question: "{msg.question}"

Provide a clear, helpful answer. If the search results don't contain enough information to answer the question, say so honestly.

Respond with a JSON object as specified in your instructions."""

        # Query LLM
        result = await llm_client.query_llm(prompt, temperature=0.3, max_tokens=800)

        if result["success"]:
            parsed = llm_client.parse_json_response(result["content"])

            if parsed and "answer" in parsed:
                response = GeneralResponse(
                    answer=parsed["answer"],
                    session_id=msg.session_id
                )
                ctx.logger.info("Generated answer for general question")
            else:
                ctx.logger.warning("Failed to parse LLM response")
                response = GeneralResponse(
                    answer="I apologize, but I'm having trouble formulating an answer right now. Could you try rephrasing your question?",
                    session_id=msg.session_id
                )

            await ctx.send(sender, response)
        else:
            ctx.logger.error(f"LLM error: {result['content']}")
            response = GeneralResponse(
                answer="I'm having trouble processing your question right now. Please try again.",
                session_id=msg.session_id
            )
            await ctx.send(sender, response)

    return agent
