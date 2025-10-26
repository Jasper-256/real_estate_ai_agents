"""
Real Estate Agent - Coordinator between all agents
"""
import asyncio
import json
from datetime import datetime
from uuid import uuid4
from uagents import Agent, Context, Model, Bureau, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)
from typing import Dict, Any, List
import os
from urllib.parse import quote
from main_agents.models import (
    ScopingRequest,
    ScopingResponse,
    ResearchRequest,
    ResearchResponse,
    GeneralRequest,
    GeneralResponse,
    MapboxRequest,
    MapboxResponse,
    LocalDiscoveryRequest,
    LocalDiscoveryResponse,
    CommunityAnalysisRequest,
    CommunityAnalysisResponse,
)
from main_agents.scoping_agent import create_scoping_agent
from main_agents.research_agent import create_research_agent
from main_agents.general_agent import create_general_agent
from main_agents.mapbox_agent import create_mapbox_agent
from main_agents.local_discovery_agent import create_local_discovery_agent
from main_agents.community_analysis_agent import create_community_analysis_agent


# Helper function to create chat messages
def create_text_chat(text: str, end_session: bool = False) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(timestamp=datetime.utcnow(), msg_id=uuid4(), content=content)


# Helper function to generate static map image URL
def generate_static_map_url(geocoded_results: List[Dict[str, Any]]) -> str:
    """
    Generate a Mapbox Static Images API URL showing all property locations.

    Args:
        geocoded_results: List of dicts with 'latitude', 'longitude', and 'index' keys

    Returns:
        Complete Mapbox Static Images API URL
    """
    mapbox_token = os.getenv("MAPBOX_API_KEY")
    if not mapbox_token or not geocoded_results:
        return None

    # Base URL for Mapbox Static Images API
    base_url = "https://api.mapbox.com/styles/v1/mapbox/streets-v12/static"

    # Create marker overlays for each property
    # Format: pin-s-{label}+{color}({lon},{lat})
    markers = []
    for result in geocoded_results:
        lat = result.get("latitude")
        lon = result.get("longitude")
        idx = result.get("index", 0)

        if lat and lon:
            # Use index + 1 as label (1-5), red color for visibility
            label = idx + 1
            # Use different colors for variety
            colors = ["e74c3c", "3498db", "2ecc71", "f39c12", "9b59b6"]  # red, blue, green, orange, purple
            color = colors[idx % len(colors)]
            markers.append(f"pin-s-{label}+{color}({lon},{lat})")

    if not markers:
        return None

    # Join all markers with commas
    overlay = ",".join(markers)

    # Use 'auto' to automatically center and zoom to fit all markers
    # Request high-res image with @2x
    image_params = "auto/1000x600@2x"

    # Construct final URL
    static_map_url = f"{base_url}/{overlay}/{image_params}?access_token={mapbox_token}"

    return static_map_url


print("=" * 60)
print("🏠 Estate Search System Starting")
print("=" * 60)

# Create all agents
scoping_agent = create_scoping_agent(port=8001)
research_agent = create_research_agent(port=8002)
general_agent = create_general_agent(port=8003)
mapbox_agent = create_mapbox_agent(port=8004)
local_discovery_agent = create_local_discovery_agent(port=8005)
community_analysis_agent = create_community_analysis_agent(port=8006)

# Create coordinator agent
coordinator = Agent(
    name="estate-search-coordinator",
    seed="estate_coordinator_seed_12332",
    mailbox=True,
)

# Store agent addresses
scoping_address = scoping_agent.address
research_address = research_agent.address
general_address = general_agent.address
mapbox_address = mapbox_agent.address
local_discovery_address = local_discovery_agent.address
community_analysis_address = community_analysis_agent.address

# Session storage
sessions = {}

# Create protocol compatible with chat protocol spec
protocol = Protocol(spec=chat_protocol_spec)


# Helper function to send final response to user
async def send_final_response(ctx: Context, session_id: str):
    """Build and send the final response with all collected data"""
    if session_id not in sessions:
        ctx.logger.error(f"Session {session_id} not found")
        return

    session = sessions[session_id]
    user_sender = session.get("user_sender")

    if not user_sender:
        ctx.logger.error(f"No user sender found for session {session_id}")
        return

    # Get all the collected data
    scoping_msg = session.get("scoping")
    research_msg = session.get("research")
    geocoded_results = session.get("geocoded_results", [])
    community_msg = session.get("community_analysis")

    if not research_msg:
        ctx.logger.error("No research data found")
        return

    # Merge geocoded data and images into raw_search_results
    enhanced_results = []
    result_images = research_msg.result_images if research_msg.result_images else []

    for idx, result in enumerate(research_msg.raw_search_results[:5]):
        enhanced_result = dict(result)

        # Find matching geocoded data
        geocoded = next((g for g in geocoded_results if g["index"] == idx), None)
        if geocoded:
            enhanced_result["latitude"] = geocoded["latitude"]
            enhanced_result["longitude"] = geocoded["longitude"]
            enhanced_result["address"] = geocoded["address"]

        # Add image URL if available
        image_data = next((img for img in result_images if img["index"] == idx), None)
        if image_data:
            enhanced_result["image_url"] = image_data["image_url"]

        enhanced_results.append(enhanced_result)

    # Format response as structured markdown
    response_text = f"# 🏠 Property Search Results\n\n"
    response_text += f"**{research_msg.search_summary}**\n\n"
    response_text += f"Found **{research_msg.total_found}** properties matching your criteria.\n\n"

    # Generate and add static map image if we have geocoded results
    if geocoded_results:
        map_url = generate_static_map_url(geocoded_results)
        if map_url:
            ctx.logger.info("Generated static map URL")
            response_text += f"## 📍 Map View\n\n"
            response_text += f"![Properties Map]({map_url})\n\n"
            response_text += "*Numbered markers correspond to properties listed below*\n\n"

    response_text += "---\n\n"

    # Format each property
    for idx, result in enumerate(enhanced_results, 1):
        response_text += f"## Property {idx}\n\n"

        # Title/Address
        if result.get("title"):
            response_text += f"### 📍 {result['title']}\n\n"

        # Image
        if result.get("image_url"):
            response_text += f"![Property Image]({result['image_url']})\n\n"

        # Price
        if result.get("price"):
            response_text += f"**💰 Price:** {result['price']}\n\n"

        # Beds/Baths/Sqft
        details = []
        if result.get("beds"):
            details.append(f"{result['beds']} beds")
        if result.get("baths"):
            details.append(f"{result['baths']} baths")
        if result.get("sqft"):
            details.append(f"{result['sqft']} sqft")

        if details:
            response_text += f"**🏡 Details:** {' | '.join(details)}\n\n"

        # Coordinates
        if result.get("latitude") and result.get("longitude"):
            response_text += f"**📌 Coordinates:** {result['latitude']}, {result['longitude']}\n\n"

        # Link
        if result.get("link"):
            response_text += f"**🔗 Listing:** {result['link']}\n\n"

        response_text += "---\n\n"

    # Add community analysis if available
    if community_msg:
        response_text += f"## 🏘️ Community Analysis: {community_msg.location}\n\n"

        if community_msg.overall_score is not None:
            response_text += f"**Overall Score:** {community_msg.overall_score}/10\n\n"

        if community_msg.overall_explanation:
            response_text += f"**Overview:** {community_msg.overall_explanation}\n\n"

        if community_msg.safety_score is not None:
            response_text += f"**🛡️ Safety Score:** {community_msg.safety_score}/10\n\n"

        if community_msg.school_rating is not None:
            response_text += f"**🎓 School Rating:** {community_msg.school_rating}/10\n"
        if community_msg.school_explanation:
            response_text += f"   *{community_msg.school_explanation}*\n\n"

        if community_msg.housing_price_per_square_foot:
            response_text += f"**💵 Housing Price per Sqft:** ${community_msg.housing_price_per_square_foot}\n\n"

        if community_msg.average_house_size_square_foot:
            response_text += f"**📏 Average House Size:** {community_msg.average_house_size_square_foot} sqft\n\n"

        if community_msg.positive_stories:
            response_text += f"**✅ Positive Highlights:**\n\n"
            for story in community_msg.positive_stories[:3]:
                if isinstance(story, dict):
                    response_text += f"- **{story.get('title', 'News')}**\n"
                    response_text += f"  {story.get('summary', '')}\n"
                    if story.get('url'):
                        response_text += f"  [Read more]({story['url']})\n"
                else:
                    response_text += f"- {story}\n"
                response_text += "\n"

        if community_msg.negative_stories:
            response_text += f"**⚠️ Considerations:**\n\n"
            for story in community_msg.negative_stories[:3]:
                if isinstance(story, dict):
                    response_text += f"- **{story.get('title', 'News')}**\n"
                    response_text += f"  {story.get('summary', '')}\n"
                    if story.get('url'):
                        response_text += f"  [Read more]({story['url']})\n"
                else:
                    response_text += f"- {story}\n"
                response_text += "\n"

    # Send final response
    await ctx.send(user_sender, create_text_chat(response_text, end_session=True))
    ctx.logger.info(f"Sent final response to {user_sender}")


@coordinator.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info("=" * 60)
    ctx.logger.info("Coordinator started")
    ctx.logger.info(f"Scoping Agent: {scoping_address}")
    ctx.logger.info(f"Research Agent: {research_address}")
    ctx.logger.info(f"General Agent: {general_address}")
    ctx.logger.info(f"Mapbox Agent: {mapbox_address}")
    ctx.logger.info(f"Local Discovery Agent: {local_discovery_address}")
    ctx.logger.info(f"Community Analysis Agent: {community_analysis_address}")
    ctx.logger.info("=" * 60)


@coordinator.on_message(model=ScopingResponse)
async def handle_scoping(ctx: Context, sender: str, msg: ScopingResponse):
    ctx.logger.info(f"Received scoping response for session {msg.session_id}")
    ctx.logger.info(f"DEBUG - is_general_question: {msg.is_general_question}")
    ctx.logger.info(f"DEBUG - general_question: {msg.general_question}")
    ctx.logger.info(f"DEBUG - is_complete: {msg.is_complete}")

    if msg.session_id not in sessions:
        sessions[msg.session_id] = {}

    sessions[msg.session_id]["scoping"] = msg

    # Get user sender to send updates
    user_sender = sessions[msg.session_id].get("user_sender")

    # Route based on intent
    if msg.is_general_question and msg.general_question:
        # Forward to general agent
        ctx.logger.info(f"Forwarding to general agent with question: {msg.general_question}")
        if user_sender:
            await ctx.send(user_sender, create_text_chat("💬 Answering your question...", end_session=False))
        await ctx.send(
            general_address,
            GeneralRequest(
                question=msg.general_question,
                session_id=msg.session_id
            )
        )
    elif msg.is_complete and msg.requirements:
        # Forward to research agent for property search
        ctx.logger.info(f"Forwarding to research agent")
        if user_sender:
            await ctx.send(user_sender, create_text_chat("🏠 Searching for properties...", end_session=False))
        await ctx.send(
            research_address,
            ResearchRequest(
                requirements=msg.requirements,
                session_id=msg.session_id
            )
        )

        # Also send to community analysis agent if we have a community name
        if msg.community_name:
            ctx.logger.info(f"Forwarding to community analysis agent for: {msg.community_name}")
            await ctx.send(
                community_analysis_address,
                CommunityAnalysisRequest(
                    location_name=msg.community_name,
                    session_id=msg.session_id
                )
            )
    else:
        # Still gathering requirements - send scoping message to user
        if user_sender and msg.agent_message:
            await ctx.send(user_sender, create_text_chat(msg.agent_message, end_session=False))


@coordinator.on_message(model=ResearchResponse)
async def handle_research(ctx: Context, sender: str, msg: ResearchResponse):
    ctx.logger.info(f"Received research response for session {msg.session_id}")

    if msg.session_id not in sessions:
        sessions[msg.session_id] = {}

    sessions[msg.session_id]["research"] = msg
    sessions[msg.session_id]["geocoded_results"] = []
    sessions[msg.session_id]["geocoding_count"] = 0

    user_sender = sessions[msg.session_id].get("user_sender")

    # If we have search results, geocode the first 5
    if msg.raw_search_results and len(msg.raw_search_results) > 0:
        # Limit to 5 for faster processing
        results_to_geocode = msg.raw_search_results[:5]
        sessions[msg.session_id]["expected_results_count"] = len(results_to_geocode)

        ctx.logger.info(f"Geocoding {len(results_to_geocode)} results")

        if user_sender:
            await ctx.send(user_sender, create_text_chat(f"📍 Found {msg.total_found} properties! Gathering location details...", end_session=False))

        for idx, result in enumerate(results_to_geocode):
            address = result.get("title", "")

            if address:
                ctx.logger.info(f"Geocoding result {idx + 1}: {address}")
                await ctx.send(
                    mapbox_address,
                    MapboxRequest(
                        address=address,
                        session_id=f"{msg.session_id}__{idx}"  # Unique ID per result
                    )
                )
    else:
        ctx.logger.info("No search results to geocode")
        # Send response immediately if no results
        if user_sender:
            await ctx.send(user_sender, create_text_chat(msg.search_summary, end_session=True))


@coordinator.on_message(model=MapboxResponse)
async def handle_mapbox(ctx: Context, sender: str, msg: MapboxResponse):
    ctx.logger.info(f"Received Mapbox response for session {msg.session_id}")

    # Parse session ID to check if it's a multi-geocoding request
    if "__" in msg.session_id:
        # This is a geocoded result for cycling through listings
        base_session_id, idx_str = msg.session_id.split("__", 1)
        idx = int(idx_str)

        if base_session_id not in sessions:
            sessions[base_session_id] = {}

        if "geocoded_results" not in sessions[base_session_id]:
            sessions[base_session_id]["geocoded_results"] = []

        # Store this geocoded result
        if not msg.error:
            ctx.logger.info(f"Geocoded result {idx + 1}: {msg.address} -> ({msg.latitude}, {msg.longitude})")
            sessions[base_session_id]["geocoded_results"].append({
                "index": idx,
                "latitude": msg.latitude,
                "longitude": msg.longitude,
                "address": msg.address
            })
        else:
            ctx.logger.warning(f"Geocoding error for result {idx + 1}: {msg.error}")

        sessions[base_session_id]["geocoding_count"] = sessions[base_session_id].get("geocoding_count", 0) + 1

        # Check if all geocoding is complete and send final response
        expected_count = sessions[base_session_id].get("expected_results_count", 0)
        geocoding_count = sessions[base_session_id]["geocoding_count"]

        ctx.logger.info(f"Geocoding progress: {geocoding_count}/{expected_count}")

        if geocoding_count >= expected_count and expected_count > 0:
            ctx.logger.info("All geocoding complete! Building final response...")
            await send_final_response(ctx, base_session_id)

    else:
        # Legacy single result geocoding
        if msg.session_id not in sessions:
            sessions[msg.session_id] = {}

        sessions[msg.session_id]["mapbox"] = msg

        if msg.error:
            ctx.logger.warning(f"Mapbox geocoding error: {msg.error}")
        else:
            ctx.logger.info(f"Geocoded: {msg.address} -> ({msg.latitude}, {msg.longitude})")


@coordinator.on_message(model=LocalDiscoveryResponse)
async def handle_local_discovery(ctx: Context, sender: str, msg: LocalDiscoveryResponse):
    ctx.logger.info(f"Received POI response for session {msg.session_id}, listing {msg.listing_index}: {len(msg.pois)} POIs")

    if msg.session_id not in sessions:
        sessions[msg.session_id] = {}

    if "poi_results" not in sessions[msg.session_id]:
        sessions[msg.session_id]["poi_results"] = []

    # Store POIs for this listing
    sessions[msg.session_id]["poi_results"].append({
        "listing_index": msg.listing_index,
        "pois": [poi.dict() for poi in msg.pois]
    })

    sessions[msg.session_id]["poi_count"] = sessions[msg.session_id].get("poi_count", 0) + 1

    # Check if all POIs are collected
    expected_count = sessions[msg.session_id].get("expected_results_count", 0)
    poi_count = sessions[msg.session_id]["poi_count"]

    ctx.logger.info(f"POI progress: {poi_count}/{expected_count}")

    # If all POIs collected, send final response
    if poi_count >= expected_count and expected_count > 0:
        ctx.logger.info("All POIs collected! Building final response...")
        await send_final_response(ctx, msg.session_id)


@coordinator.on_message(model=GeneralResponse)
async def handle_general(ctx: Context, sender: str, msg: GeneralResponse):
    ctx.logger.info(f"Received general response for session {msg.session_id}")

    if msg.session_id not in sessions:
        sessions[msg.session_id] = {}

    sessions[msg.session_id]["general"] = msg

    # Send response back to user
    if "user_sender" in sessions[msg.session_id]:
        user_sender = sessions[msg.session_id]["user_sender"]
        await ctx.send(user_sender, create_text_chat(msg.answer, end_session=True))


@coordinator.on_message(model=CommunityAnalysisResponse)
async def handle_community_analysis(ctx: Context, sender: str, msg: CommunityAnalysisResponse):
    ctx.logger.info(f"Received community analysis response for session {msg.session_id}")

    if msg.session_id not in sessions:
        sessions[msg.session_id] = {}

    sessions[msg.session_id]["community_analysis"] = msg


# Chat protocol handlers
@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    # Send acknowledgement immediately
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(), acknowledged_msg_id=msg.msg_id),
    )

    text = msg.text()
    if not text:
        return

    # Use sender address as session ID for persistent conversation history
    session_id = sender

    ctx.logger.info(f"Received chat message from {sender}: {text}")
    ctx.logger.info(f"Using session ID: {session_id}")

    # Initialize session and store sender for later response
    if session_id not in sessions:
        sessions[session_id] = {}
        ctx.logger.info(f"New session created for {sender}")
    else:
        ctx.logger.info(f"Continuing existing session for {sender}")

    sessions[session_id]["user_sender"] = sender

    try:
        # Send initial status update
        await ctx.send(sender, create_text_chat("🔍 Processing your request...", end_session=False))

        # Send to scoping agent - it will maintain conversation history by session_id
        ctx.logger.info("Routing message to scoping agent")
        await ctx.send(
            scoping_address,
            ScopingRequest(
                user_message=text,
                session_id=session_id
            )
        )

        # Don't wait - let the individual handlers send responses as they complete

    except Exception as e:
        ctx.logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        await ctx.send(sender, create_text_chat(f"An error occurred: {str(e)}", end_session=True))


@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    # Not interested in acknowledgements for this example
    pass


# Attach protocol to coordinator
coordinator.include(protocol, publish_manifest=True)

# Create Bureau to run all agents
bureau = Bureau(port=8080, endpoint="http://localhost:8080/submit")
bureau.add(scoping_agent)
bureau.add(research_agent)
bureau.add(general_agent)
bureau.add(mapbox_agent)
bureau.add(local_discovery_agent)
bureau.add(community_analysis_agent)
bureau.add(coordinator)

print("✅ All agents configured")
print(f"   - Coordinator: {coordinator.address}")
print(f"   - Scoping: {scoping_address}")
print(f"   - Research: {research_address}")
print(f"   - General: {general_address}")
print(f"   - Mapbox: {mapbox_address}")
print(f"   - Local Discovery: {local_discovery_address}")
print(f"   - Community Analysis: {community_analysis_address}")
print("=" * 60)

if __name__ == "__main__":
    bureau.run()
