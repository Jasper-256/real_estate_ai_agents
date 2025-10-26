"""
Research Agent - Searches for property listings and generates a summary
"""
from datetime import datetime
from uuid import uuid4

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)
from brightdata_client import BrightDataClient
import aiohttp, os, json
from dotenv import load_dotenv
load_dotenv()

ASI_API_KEY = os.getenv("ASI_API_KEY")
ASI_URL = "https://api.asi1.ai/v1/chat/completions"
BRIGHTDATA_TOKEN = os.getenv("BRIGHT_DATA_API_KEY")


def create_text_chat(text: str, end_session: bool = False) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(timestamp=datetime.utcnow(), msg_id=uuid4(), content=content)


def extract_first_image_from_markdown(markdown: str) -> str | None:
    """Extract the first image URL from markdown content."""
    import re
    # Look for markdown image syntax: ![alt](url)
    img_pattern = r'!\[.*?\]\((https?://[^\)]+)\)'
    matches = re.findall(img_pattern, markdown)

    if matches:
        # Filter for likely property images (avoid icons, logos, etc.)
        for url in matches:
            # Skip small images, icons, and logos
            if any(skip in url.lower() for skip in ['icon', 'logo', 'avatar', 'badge', 'button']):
                continue
            # Skip very small dimensions in URL
            if any(size in url.lower() for size in ['16x16', '32x32', '48x48', '64x64']):
                continue
            return url

    return None


async def generate_llm_summary(search_results: list, user_query: str) -> str:
    """Use ASI-1 to generate a conversational summary from search results."""
    headers = {
        "Authorization": f"Bearer {ASI_API_KEY}",
        "Content-Type": "application/json",
    }

    # Format search results
    results_text = ""
    for i, result in enumerate(search_results[:8], 1):
        title = result.get("title", "")
        description = result.get("description", "")
        link = result.get("link", "")
        results_text += f"{i}. {title}\n"
        if description:
            results_text += f"   {description}\n"
        results_text += f"   Link: {link}\n\n"

    body = {
        "model": "asi-1",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a friendly real estate research assistant. Based on search results, "
                    "provide a natural, conversational summary of available properties. "
                    "Mention 2-3 specific listings with addresses and key details. "
                    "Keep it warm and helpful, 3-4 sentences max."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"User query: {user_query}\n\n"
                    f"Search results:\n{results_text}\n"
                    "Summarize what properties are available."
                ),
            },
        ],
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(ASI_URL, headers=headers, json=body) as resp:
                if resp.status != 200:
                    return f"Found {len(search_results)} property listings. Check the search results for details!"

                res = await resp.json()
                if "choices" in res and res["choices"]:
                    return res["choices"][0]["message"]["content"]
                else:
                    return f"Found {len(search_results)} property listings. Check the search results for details!"
    except Exception as e:
        print(f"[LLM Summary Error] {e}")
        return f"Found {len(search_results)} property listings. Check the search results for details!"


# Initialize BrightData client
brightdata = BrightDataClient()

# Create agent with mailbox for agentverse
agent = Agent(
    name="Research Agent",
    seed="research_agent_seed_1232233",
    mailbox=True,
)

# Create protocol compatible with chat protocol spec
protocol = Protocol(spec=chat_protocol_spec)


# Handler for chat messages
@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    # Send acknowledgement for receiving the message
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(), acknowledged_msg_id=msg.msg_id),
    )

    text = msg.text()
    if not text:
        return

    try:
        ctx.logger.info(f"Received property search query: {text}")

        # Build search query - the user's text is already natural language
        # Just append "homes for sale" if not already mentioned
        prompt = text
        if "homes" not in text.lower() and "properties" not in text.lower() and "real estate" not in text.lower():
            prompt = f"{text} homes for sale"

        ctx.logger.info(f"Search query: {prompt}")

        # Call Bright Data MCP with search_engine tool
        result = await brightdata.call("search_engine", {"query": prompt, "engine": "google"})

        if not result["success"]:
            response = f"Search failed: {result.get('error', 'Unknown error')}. Please try again."
            await ctx.send(sender, create_text_chat(response, end_session=True))
            return

        # Parse the response to extract property listings
        raw_output = result.get("output", "")
        ctx.logger.info(f"Raw Bright Data output: {raw_output[:500]}...")

        organic_results = []
        result_images = []

        try:
            # Try to parse as JSON first
            data = json.loads(raw_output)

            # Handle different response formats
            if isinstance(data, dict):
                # Search engine results format
                if "organic" in data:
                    organic_results = data.get("organic", [])
                    ctx.logger.info(f"Found {len(organic_results)} organic search results")

                    # Try to scrape the first 3 results for images
                    results_to_scrape = organic_results[:3]
                    ctx.logger.info(f"Scraping {len(results_to_scrape)} results for images")

                    for idx, result in enumerate(results_to_scrape):
                        result_url = result.get("link", "")
                        if result_url and ("redfin.com" in result_url or "zillow.com" in result_url):
                            ctx.logger.info(f"Scraping result {idx + 1} for images: {result_url}")
                            try:
                                scrape_result = await brightdata.call(
                                    "scrape_as_markdown",
                                    {"url": result_url}
                                )
                                if scrape_result["success"]:
                                    markdown = scrape_result.get("output", "")
                                    # Extract first image URL from markdown
                                    image_url = extract_first_image_from_markdown(markdown)
                                    if image_url:
                                        ctx.logger.info(f"Found image for result {idx + 1}: {image_url[:100]}")
                                        result_images.append({"index": idx, "image_url": image_url})
                                    else:
                                        ctx.logger.info(f"No image found for result {idx + 1}")
                                else:
                                    ctx.logger.warning(f"Scrape failed for result {idx + 1}")
                            except Exception as e:
                                ctx.logger.warning(f"Failed to scrape result {idx + 1}: {e}")
                        else:
                            ctx.logger.info(f"Skipping result {idx + 1} (not Redfin/Zillow)")

        except json.JSONDecodeError:
            ctx.logger.warning("Could not parse response as JSON")

        # Build summary using LLM if we have organic results
        if organic_results and len(organic_results) > 0:
            ctx.logger.info("Generating LLM summary from search results")
            summary = await generate_llm_summary(organic_results, text)

            # Ensure summary mentions count
            if not any(word in summary.lower() for word in ['found', 'results', 'listings', 'properties']):
                summary = f"Found {len(organic_results)} property listings. {summary}"

            # Add top 5 links
            summary += "\n\nTop results:"
            for i, result in enumerate(organic_results[:5], 1):
                title = result.get("title", "Unknown")
                link = result.get("link", "")
                summary += f"\n{i}. {title}\n   {link}"

            response = summary
        else:
            response = "No properties found matching your search. Try adjusting your search terms."

    except Exception as e:
        ctx.logger.exception('Error processing property search')
        response = f"An error occurred while searching for properties. Please try again later. {e}"

    await ctx.send(sender, create_text_chat(response, end_session=True))


@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    # We are not interested in the acknowledgements for this example
    pass


# Attach the protocol to the agent
agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
