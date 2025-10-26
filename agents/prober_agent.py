"""
Prober Agent - Gathers intelligence about properties for negotiation leverage
"""

from datetime import datetime
from uuid import uuid4

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)
from tavily_client import TavilyClient
from brightdata_client import BrightDataClient
from llm_client import SimpleLLMAgent


class ProberLLMAgent(SimpleLLMAgent):
    """LLM agent specialized for analyzing property intelligence and extracting negotiation leverage"""

    def __init__(self):
        system_prompt = """You are a real estate negotiation analyst. Extract actionable intelligence from property data.
Return ONLY valid JSON, no markdown formatting or additional text."""
        super().__init__(name="ProberLLM", system_prompt=system_prompt)

    async def analyze_property_intel(self, address: str, scraped_content: list) -> dict:
        """
        Analyze scraped property content and extract negotiation leverage.
        Returns structured findings.
        """
        # Format scraped content for LLM
        content_summary = ""
        for idx, item in enumerate(scraped_content, 1):
            url = item.get("url", "Unknown")
            text = item.get("content", "")[:2000]  # Limit to first 2000 chars per source
            content_summary += f"\n\n--- Source {idx}: {url} ---\n{text}\n"

        prompt = f"""You are a ruthless real estate negotiation analyst. Your job is to find NEGATIVE information, red flags, and weaknesses about this property that a buyer can use as leverage to negotiate a LOWER price.

Property Address: {address}

Scraped Information:
{content_summary}

FOCUS ON NEGATIVE INFORMATION ONLY. Extract leverage points in these categories:

1. **time_on_market**:
   - How many days on market? (longer = desperate seller)
   - Price reductions? (indicates overpriced or lack of interest)
   - Multiple listing attempts?

2. **price_history**:
   - Recent price drops
   - Bought high, selling low (financial pressure)
   - Overpriced compared to comps

3. **property_issues**:
   - Foundation, roof, plumbing problems
   - Code violations, unpermitted work
   - Deferred maintenance
   - Needed repairs mentioned in listing

4. **owner_situation**:
   - Foreclosure risk, tax liens
   - Estate sale (heirs want quick cash)
   - Divorce (forced sale)
   - Job relocation (time pressure)
   - Financial distress signals

5. **market_conditions**:
   - Buyer's market indicators
   - High inventory in area
   - Declining neighborhood values
   - Economic factors favoring buyers

**IMPORTANT**: Only include findings that give the BUYER an advantage. Skip positive information. Be specific with numbers (days on market, price reductions, etc).

For each finding, provide:
- category (one of the above)
- summary (1-2 sentences highlighting the NEGATIVE aspect)
- leverage_score (0-10, how useful for negotiation - higher = more leverage)
- details (specific numbers, dates, problems)
- source_url (if applicable)

Also provide:
- overall_assessment: A 2-3 sentence summary of the buyer's negotiation position focusing on WEAKNESSES found
- leverage_score: Overall score 0-10 (10 = strong buyer leverage due to many issues found)

Return ONLY valid JSON in this exact format:
{{
  "findings": [
    {{
      "category": "time_on_market",
      "summary": "...",
      "leverage_score": 7.5,
      "details": "...",
      "source_url": "..."
    }}
  ],
  "overall_assessment": "...",
  "leverage_score": 6.5
}}

If you cannot find any information, return an empty findings array and low leverage_score.
"""

        result = await self.query_with_json(prompt, temperature=0.3)

        if result["success"]:
            return result["data"]
        else:
            return {
                "findings": [],
                "overall_assessment": f"Analysis failed: {result.get('error', 'Unknown error')}",
                "leverage_score": 0.0
            }


# Initialize the agent clients
tavily = TavilyClient()
brightdata = BrightDataClient()
llm_agent = ProberLLMAgent()

# Create the agent
agent = Agent(
    name="Prober Agent",
    seed="prober_agent_seed_1234532323",
    mailbox=True,
)

# Create protocol compatible with chat protocol spec
protocol = Protocol(spec=chat_protocol_spec)


# Define the handler for chat messages
@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    # Send acknowledgement for receiving the message
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(), acknowledged_msg_id=msg.msg_id),
    )

    # Extract the property address from the text
    text = ''
    for item in msg.content:
        if isinstance(item, TextContent):
            text += item.text

    # The text should contain a property address
    address = text.strip()

    ctx.logger.info(f"Probing property: {address}")

    # Perform analysis
    response_text = 'I am afraid something went wrong and I am unable to analyze the property at the moment'

    try:
        # Step 1: Use Tavily to find relevant sources about this property
        ctx.logger.info(f"Tavily search: {address} property history")
        tavily_result = await tavily.search(
            query=f"{address} property history price",
            search_depth="basic",
            max_results=2
        )

        all_urls = []
        if tavily_result.get("success"):
            results = tavily_result.get("results", [])
            for result in results:
                url = result.get("url")
                # Skip Zillow and Redfin as they're already covered by research agent
                if url and "zillow.com" not in url.lower() and "redfin.com" not in url.lower():
                    all_urls.append({
                        "url": url,
                        "title": result.get("title", ""),
                        "content": result.get("content", "")
                    })
        else:
            ctx.logger.warning(f"Tavily search failed: {tavily_result.get('error')}")

        ctx.logger.info(f"Found {len(all_urls)} unique URLs from Tavily (excluding Zillow/Redfin)")

        # Step 2: Use BrightData to scrape the top URLs (limit to 2-3 max)
        scraped_content = []
        urls_to_scrape = all_urls[:3]  # Max 3 sources

        for item in urls_to_scrape:
            url = item["url"]
            ctx.logger.info(f"Scraping with BrightData: {url}")

            try:
                scrape_result = await brightdata.call(
                    "scrape_as_markdown",
                    {"url": url}
                )

                if scrape_result.get("success"):
                    markdown_content = scrape_result.get("output", "")
                    scraped_content.append({
                        "url": url,
                        "title": item["title"],
                        "content": markdown_content,
                        "tavily_snippet": item["content"]
                    })
                    ctx.logger.info(f"Successfully scraped {url}")
                else:
                    ctx.logger.warning(f"BrightData scrape failed for {url}: {scrape_result.get('error')}")
                    # Fall back to Tavily content
                    scraped_content.append({
                        "url": url,
                        "title": item["title"],
                        "content": item["content"],
                        "tavily_snippet": item["content"]
                    })
            except Exception as e:
                ctx.logger.warning(f"Error scraping {url}: {e}")
                # Fall back to Tavily content
                scraped_content.append({
                    "url": url,
                    "title": item["title"],
                    "content": item["content"],
                    "tavily_snippet": item["content"]
                })

        ctx.logger.info(f"Scraped {len(scraped_content)} sources")

        # Step 3: Use LLM to analyze and extract negotiation leverage
        ctx.logger.info("Analyzing content with LLM...")
        analysis = await llm_agent.analyze_property_intel(address, scraped_content)

        # Format the response as readable text
        findings = analysis.get("findings", [])
        leverage_score = analysis.get("leverage_score", 0.0)
        overall_assessment = analysis.get("overall_assessment", "No assessment available")

        response_text = f"**Property Intelligence Report: {address}**\n\n"
        response_text += f"**Overall Leverage Score: {leverage_score}/10**\n\n"
        response_text += f"**Assessment:** {overall_assessment}\n\n"

        if findings:
            response_text += "**Key Findings:**\n\n"
            for idx, finding in enumerate(findings, 1):
                response_text += f"{idx}. **{finding['category'].replace('_', ' ').title()}** (Score: {finding['leverage_score']}/10)\n"
                response_text += f"   - {finding['summary']}\n"
                response_text += f"   - Details: {finding['details']}\n"
                if finding.get('source_url'):
                    response_text += f"   - Source: {finding['source_url']}\n"
                response_text += "\n"
        else:
            response_text += "No significant leverage points found.\n"

        ctx.logger.info(f"Analysis complete with {len(findings)} findings")

    except Exception as e:
        ctx.logger.exception(f'Error analyzing property: {e}')

    # Send the response back to the user
    await ctx.send(sender, ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=[
            # Send the analysis as text
            TextContent(type="text", text=response_text),
            # Signal that the session is over
            EndSessionContent(type="end-session"),
        ]
    ))


@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    # We are not interested in acknowledgements for this example
    pass


# Attach the protocol to the agent
agent.include(protocol, publish_manifest=True)


if __name__ == "__main__":
    agent.run()
