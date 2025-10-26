from uagents import Agent, Context
from .models import ResearchRequest, ResearchResponse, PropertyListing
from .brightdata_client import BrightDataClient
import aiohttp, os, json


ASI_API_KEY = os.getenv("ASI_API_KEY")
ASI_URL = "https://api.asi1.ai/v1/chat/completions"
BRIGHTDATA_TOKEN = os.getenv("BRIGHT_DATA_API_KEY")


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


async def generate_llm_summary(search_results: list, requirements, original_query: str) -> str:
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

    # Build requirement summary
    req_parts = [requirements.location]
    if requirements.bedrooms:
        req_parts.append(f"{requirements.bedrooms} bedrooms")
    if requirements.bathrooms:
        req_parts.append(f"{requirements.bathrooms} bathrooms")
    if requirements.budget_max:
        mil = requirements.budget_max / 1000000
        req_parts.append(f"budget under ${mil:.1f}M")
    req_text = ", ".join(req_parts)

    body = {
        "model": "asi-1",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a friendly real estate assistant. Based on search results, "
                    "provide a natural, conversational summary of available properties. "
                    "Mention 2-3 specific listings with addresses and key details. "
                    "Keep it warm and helpful, 3-4 sentences max."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"User is looking for: {req_text}\n\n"
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
                    return f"Found {len(search_results)} property listings in {requirements.location}. Check the search results for details!"

                res = await resp.json()
                if "choices" in res and res["choices"]:
                    return res["choices"][0]["message"]["content"]
                else:
                    return f"Found {len(search_results)} property listings in {requirements.location}. Check the search results for details!"
    except Exception as e:
        ctx_logger = None  # We don't have ctx here, so just print
        print(f"[LLM Summary Error] {e}")
        return f"Found {len(search_results)} property listings in {requirements.location}. Check the search results for details!"


async def decide_tool(prompt: str) -> dict:
    """Ask ASI-1 which MCP tool to use. Returns fallback plan on error."""
    headers = {
        "Authorization": f"Bearer {ASI_API_KEY}",
        "Content-Type": "application/json",
    }

    body = {
        "model": "asi-1-mini",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a planning model for Bright Data MCP. "
                    "Given a user query, output JSON {tool:'', arguments:{}} only."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(ASI_URL, headers=headers, json=body) as resp:
            status = resp.status
            try:
                res = await resp.json()
            except Exception:
                text = await resp.text()
                return {"tool": "search_engine", "arguments": {"query": prompt}, "error": f"Bad JSON: {text}"}

    # 🔎 Debug: if API returned an error, log and fall back
    if "choices" not in res:
        print(f"[ASI-1 ERROR] status={status}, response={res}")
        return {"tool": "search_engine", "arguments": {"query": prompt}, "error": res.get("error", res)}

    # ✅ Extract output safely
    raw = res["choices"][0]["message"]["content"]
    try:
        return json.loads(raw)
    except Exception:
        return {"tool": "search_engine", "arguments": {"query": prompt}}

def create_research_agent(port: int = 8002):
    agent = Agent(
        name="research_agent",
        port=port,
        seed="research_agent_seed",
        endpoint=[f"http://localhost:{port}/submit"],
    )

    brightdata = BrightDataClient()

    @agent.on_event("startup")
    async def startup(ctx: Context):
        ctx.logger.info(f"Research Agent started at {ctx.agent.address}")

    @agent.on_message(model=ResearchRequest)
    async def handle_request(ctx: Context, sender: str, msg: ResearchRequest):
        req = msg.requirements

        # Build search query for Bright Data - simpler, more natural query
        prompt_parts = [req.location]

        # Only add CA if not already in location
        if "CA" not in req.location.upper() and "CALIFORNIA" not in req.location.upper():
            prompt_parts.append("California")

        if req.bedrooms:
            prompt_parts.append(f"{req.bedrooms} bedroom")
        if req.bathrooms:
            prompt_parts.append(f"{req.bathrooms} bath")

        prompt_parts.append("homes for sale")

        if req.budget_max and req.budget_max < 1000000:
            prompt_parts.append(f"under ${req.budget_max//1000}k")
        elif req.budget_max:
            mil = req.budget_max / 1000000
            prompt_parts.append(f"under ${mil:.1f}M")

        prompt = " ".join(prompt_parts)

        ctx.logger.info(f"Search query: {prompt}")

        # Call Bright Data MCP with search_engine tool
        result = await brightdata.call("search_engine", {"query": prompt, "engine": "google"})

        if not result["success"]:
            await ctx.send(sender, ResearchResponse(
                properties=[],
                search_summary=f"Search failed: {result.get('error', 'Unknown error')}",
                total_found=0,
                session_id=msg.session_id
            ))
            return

        # Parse the response to extract property listings
        raw_output = result.get("output", "")
        ctx.logger.info(f"Raw Bright Data output: {raw_output[:500]}...")

        properties = []
        organic_results = []
        result_images = []  # Store images for all results

        try:
            # Try to parse as JSON first
            data = json.loads(raw_output)

            # Handle different response formats
            if isinstance(data, dict):
                # Search engine results format
                if "organic" in data:
                    organic_results = data.get("organic", [])
                    ctx.logger.info(f"Found {len(organic_results)} organic search results")

                    # Try to scrape the first 5 results for images
                    results_to_scrape = organic_results[:5]
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

                # Direct property listings format (if available)
                if "properties" in data:
                    for prop_data in data.get("properties", []):
                        try:
                            listing = PropertyListing(
                                address=prop_data.get("address", "Unknown"),
                                city=prop_data.get("city", req.location),
                                price=prop_data.get("price"),
                                bedrooms=prop_data.get("bedrooms"),
                                bathrooms=prop_data.get("bathrooms"),
                                sqft=prop_data.get("sqft"),
                                description=prop_data.get("description"),
                                url=prop_data.get("url"),
                                latitude=None,
                                longitude=None
                            )
                            properties.append(listing)
                        except Exception as e:
                            ctx.logger.warning(f"Skipping invalid property: {e}")

        except json.JSONDecodeError:
            ctx.logger.warning("Could not parse response as JSON")

        # Build summary - use LLM if we have organic results
        total_results = len(organic_results) if organic_results else len(properties)

        if organic_results and len(organic_results) > 0:
            ctx.logger.info("Generating LLM summary from search results")
            summary = await generate_llm_summary(organic_results, req, prompt)

            # Ensure summary mentions count
            if not any(word in summary.lower() for word in ['found', 'results', 'listings', 'properties']):
                summary = f"Found {len(organic_results)} property listings. {summary}"

        elif properties:
            summary = f"Found {len(properties)} properties in {req.location}"
            if req.bedrooms:
                summary += f" with {req.bedrooms} bedrooms"
            if req.bathrooms:
                summary += f" and {req.bathrooms} bathrooms"
            if req.budget_max:
                mil = req.budget_max / 1000000
                summary += f" under ${mil:.1f}M"
        else:
            summary = f"No properties found matching your criteria. Try adjusting your search parameters."

        # For backwards compatibility, keep top_result_image as the first image
        top_result_image = result_images[0]["image_url"] if result_images else None

        await ctx.send(sender, ResearchResponse(
            properties=properties,
            search_summary=summary,
            total_found=total_results,
            session_id=msg.session_id,
            raw_search_results=organic_results if organic_results else None,
            top_result_image_url=top_result_image,
            result_images=result_images if result_images else None
        ))

    return agent


def parse_zillow_markdown(markdown: str, requirements) -> list:
    """Parse Zillow markdown to extract property listings"""
    properties = []
    lines = markdown.split("\n")

    current_property = {}

    for line in lines:
        # Look for addresses in links
        if ("St," in line or "Ave," in line or "Rd," in line or
            "Blvd," in line or "APT" in line or "Way," in line):

            if current_property and "address" in current_property:
                # Save previous property
                try:
                    listing = PropertyListing(**current_property)
                    properties.append(listing)
                except:
                    pass
                current_property = {}

            # Extract address and URL from markdown link
            if "](https://" in line:
                start = line.find("[") + 1
                end = line.find("](")
                address = line[start:end].strip()

                url_start = line.find("](") + 2
                url_end = line.find(")", url_start)
                url = line[url_start:url_end]

                current_property["address"] = address
                current_property["url"] = url

                # Extract city
                if ", CA " in address or ",CA " in address:
                    parts = address.split(",")
                    if len(parts) >= 2:
                        current_property["city"] = parts[-2].strip()

        # Look for price
        elif line.strip().startswith("$") and current_property:
            price_str = line.strip().replace("$", "").replace(",", "")
            try:
                current_property["price"] = int(price_str)
            except:
                pass

        # Look for beds/baths/sqft
        elif "**" in line and ("bd" in line or "ba" in line) and current_property:
            # Extract bedrooms
            if "bds" in line or "bd" in line:
                try:
                    # Find pattern like "**2** bds"
                    parts = line.split("**")
                    for i, part in enumerate(parts):
                        if "bd" in parts[i+1] if i+1 < len(parts) else "":
                            current_property["bedrooms"] = int(part.strip())
                            break
                except:
                    pass

            # Extract bathrooms
            if "ba" in line:
                try:
                    parts = line.split("**")
                    for i, part in enumerate(parts):
                        next_part = parts[i+1] if i+1 < len(parts) else ""
                        if "ba" in next_part and "bd" not in next_part:
                            current_property["bathrooms"] = float(part.strip())
                            break
                except:
                    pass

            # Extract sqft
            if "sqft" in line:
                try:
                    sqft_idx = line.find("sqft")
                    before_sqft = line[:sqft_idx]
                    parts = before_sqft.split("**")
                    sqft_str = parts[-2].replace(",", "").strip()
                    current_property["sqft"] = int(sqft_str)
                except:
                    pass

    # Add last property
    if current_property and "address" in current_property:
        try:
            listing = PropertyListing(**current_property)
            properties.append(listing)
        except:
            pass

    # Filter by requirements
    filtered = []
    for prop in properties:
        # Filter by budget
        if requirements.budget_max and prop.price and prop.price > requirements.budget_max:
            continue

        # Filter by bedrooms
        if requirements.bedrooms and prop.bedrooms and prop.bedrooms != requirements.bedrooms:
            continue

        # Filter by bathrooms
        if requirements.bathrooms and prop.bathrooms and prop.bathrooms < requirements.bathrooms:
            continue

        filtered.append(prop)

    return filtered
