"""
Estate Search Main - Coordinator with REST API
"""
import asyncio
from uagents import Agent, Context, Model, Bureau
from typing import Dict, Any
from agents.models import (
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
from agents.scoping_agent import create_scoping_agent
from agents.research_agent import create_research_agent
from agents.general_agent import create_general_agent
from agents.mapbox_agent import create_mapbox_agent
from agents.local_discovery_agent import create_local_discovery_agent
from agents.community_analysis_agent import create_community_analysis_agent


# REST API Models
class ChatRequest(Model):
    message: str
    session_id: str


class ChatResponse(Model):
    status: str
    data: Dict[str, Any]


def main():
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
        name="coordinator",
        port=8080,
        seed="coordinator_seed",
        endpoint=["http://localhost:8080/submit"]
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

    @coordinator.on_event("startup")
    async def startup(ctx: Context):
        ctx.logger.info("=" * 60)
        ctx.logger.info("Coordinator started")
        ctx.logger.info(f"Scoping Agent: {scoping_address}")
        ctx.logger.info(f"Research Agent: {research_address}")
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

        # Route based on intent
        if msg.is_general_question and msg.general_question:
            # Forward to general agent
            ctx.logger.info(f"Forwarding to general agent with question: {msg.general_question}")
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

    @coordinator.on_message(model=ResearchResponse)
    async def handle_research(ctx: Context, sender: str, msg: ResearchResponse):
        ctx.logger.info(f"Received research response for session {msg.session_id}")

        if msg.session_id not in sessions:
            sessions[msg.session_id] = {}

        sessions[msg.session_id]["research"] = msg
        sessions[msg.session_id]["geocoded_results"] = []
        sessions[msg.session_id]["geocoding_count"] = 0
        sessions[msg.session_id]["poi_results"] = []
        sessions[msg.session_id]["poi_count"] = 0

        # If we have search results, geocode the first 5
        if msg.raw_search_results and len(msg.raw_search_results) > 0:
            # Limit to 5 for faster processing
            results_to_geocode = msg.raw_search_results[:5]
            ctx.logger.info(f"Geocoding {len(results_to_geocode)} results")

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

                # Trigger POI search for this location
                ctx.logger.info(f"Triggering POI search for listing {idx + 1}")
                await ctx.send(
                    local_discovery_address,
                    LocalDiscoveryRequest(
                        latitude=msg.latitude,
                        longitude=msg.longitude,
                        session_id=base_session_id,
                        listing_index=idx
                    )
                )
            else:
                ctx.logger.warning(f"Geocoding error for result {idx + 1}: {msg.error}")

            sessions[base_session_id]["geocoding_count"] = sessions[base_session_id].get("geocoding_count", 0) + 1

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

    @coordinator.on_message(model=GeneralResponse)
    async def handle_general(ctx: Context, sender: str, msg: GeneralResponse):
        ctx.logger.info(f"Received general response for session {msg.session_id}")

        if msg.session_id not in sessions:
            sessions[msg.session_id] = {}

        sessions[msg.session_id]["general"] = msg

    @coordinator.on_message(model=CommunityAnalysisResponse)
    async def handle_community_analysis(ctx: Context, sender: str, msg: CommunityAnalysisResponse):
        ctx.logger.info(f"Received community analysis response for session {msg.session_id}")

        if msg.session_id not in sessions:
            sessions[msg.session_id] = {}

        sessions[msg.session_id]["community_analysis"] = msg

    @coordinator.on_rest_post("/api/chat", ChatRequest, ChatResponse)
    async def handle_chat(ctx: Context, req: ChatRequest) -> ChatResponse:
        ctx.logger.info(f"REST request from session {req.session_id}: {req.message}")

        # Initialize session
        if req.session_id not in sessions:
            sessions[req.session_id] = {}

        try:
            # Clear old responses for this request
            sessions[req.session_id].pop("scoping", None)
            sessions[req.session_id].pop("research", None)

            # ALWAYS send every new user message to scoping agent first
            # The scoping agent will determine if we need to gather more info or search
            ctx.logger.info("Routing message to scoping agent")
            await ctx.send(
                scoping_address,
                ScopingRequest(
                    user_message=req.message,
                    session_id=req.session_id
                )
            )

            # Wait for scoping response
            for _ in range(60):
                if "scoping" in sessions[req.session_id]:
                    break
                await asyncio.sleep(0.5)
            else:
                return ChatResponse(
                    status="error",
                    data={"message": "Timeout waiting for scoping agent"}
                )

            scoping_msg = sessions[req.session_id]["scoping"]

            # Handle general question
            if scoping_msg.is_general_question:
                ctx.logger.info("Waiting for general agent response")

                for _ in range(60):
                    if "general" in sessions[req.session_id]:
                        break
                    await asyncio.sleep(0.5)

                if "general" in sessions[req.session_id]:
                    general_msg = sessions[req.session_id]["general"]
                    return ChatResponse(
                        status="success",
                        data={
                            "requirements": {},
                            "properties": [],
                            "search_summary": general_msg.answer,
                            "total_found": 0
                        }
                    )

            # Handle property search
            if scoping_msg.is_complete and scoping_msg.requirements:
                ctx.logger.info("Waiting for research results")

                for _ in range(60):
                    if "research" in sessions[req.session_id]:
                        break
                    await asyncio.sleep(0.5)

                # Also wait for community analysis if we have a community name
                if scoping_msg.community_name:
                    ctx.logger.info("Waiting for community analysis results")
                    for _ in range(60):
                        if "community_analysis" in sessions[req.session_id]:
                            break
                        await asyncio.sleep(0.5)

                if "research" in sessions[req.session_id]:
                    research_msg = sessions[req.session_id]["research"]

                    # Wait for Mapbox geocoding if we have search results
                    if research_msg.raw_search_results and len(research_msg.raw_search_results) > 0:
                        results_count = min(len(research_msg.raw_search_results), 5)
                        ctx.logger.info(f"Waiting for {results_count} geocoding results")

                        # Wait up to 15 seconds for all geocoding to complete
                        for _ in range(30):
                            geocoding_count = sessions[req.session_id].get("geocoding_count", 0)
                            if geocoding_count >= results_count:
                                ctx.logger.info(f"All {results_count} results geocoded")
                                break
                            await asyncio.sleep(0.5)
                        else:
                            ctx.logger.warning(f"Timeout: only {sessions[req.session_id].get('geocoding_count', 0)}/{results_count} results geocoded")

                        # Wait for POI searches to complete (up to 20 more seconds)
                        ctx.logger.info(f"Waiting for POI results for {results_count} listings")
                        for _ in range(40):
                            poi_count = sessions[req.session_id].get("poi_count", 0)
                            if poi_count >= results_count:
                                ctx.logger.info(f"All {results_count} POI searches complete")
                                break
                            await asyncio.sleep(0.5)
                        else:
                            ctx.logger.warning(f"Timeout: only {sessions[req.session_id].get('poi_count', 0)}/{results_count} POI searches completed")

                    # Merge geocoded data, images, and POIs into raw_search_results
                    enhanced_results = []
                    geocoded_results = sessions[req.session_id].get("geocoded_results", [])
                    result_images = research_msg.result_images if research_msg.result_images else []
                    poi_results = sessions[req.session_id].get("poi_results", [])

                    ctx.logger.info(f"🔍 Merging data - Geocoded: {len(geocoded_results)}, Images: {len(result_images)}, POI results: {len(poi_results)}")

                    for idx, result in enumerate(research_msg.raw_search_results[:5]):
                        enhanced_result = dict(result)  # Copy the original result

                        # Find matching geocoded data
                        geocoded = next((g for g in geocoded_results if g["index"] == idx), None)

                        if geocoded:
                            enhanced_result["latitude"] = geocoded["latitude"]
                            enhanced_result["longitude"] = geocoded["longitude"]
                            enhanced_result["address"] = geocoded["address"]

                        # Add image URL if available for this result
                        image_data = next((img for img in result_images if img["index"] == idx), None)
                        if image_data:
                            enhanced_result["image_url"] = image_data["image_url"]
                            ctx.logger.info(f"Added image to result {idx + 1}")

                        # Add POIs if available for this result
                        poi_data = next((p for p in poi_results if p["listing_index"] == idx), None)
                        if poi_data:
                            enhanced_result["pois"] = poi_data["pois"]
                            ctx.logger.info(f"✅ Added {len(poi_data['pois'])} POIs to result {idx + 1}")
                        else:
                            enhanced_result["pois"] = []
                            ctx.logger.warning(f"⚠️ No POI data found for result {idx + 1}")

                        # IMPORTANT: Add to results array
                        enhanced_results.append(enhanced_result)

                    ctx.logger.info(f"📊 Total enhanced results: {len(enhanced_results)}")
                    for idx, result in enumerate(enhanced_results):
                        ctx.logger.info(f"   Result {idx + 1}: {result.get('title', 'No title')[:50]}, POIs: {len(result.get('pois', []))}")

                    # Build top_result_coordinates from first geocoded result
                    top_result_coords = None
                    if len(enhanced_results) > 0 and "latitude" in enhanced_results[0]:
                        top_result_coords = {
                            "latitude": enhanced_results[0]["latitude"],
                            "longitude": enhanced_results[0]["longitude"],
                            "address": enhanced_results[0].get("address", enhanced_results[0].get("title", "")),
                            "image_url": enhanced_results[0].get("image_url")
                        }

                    # Build community analysis data if available
                    community_data = None
                    if "community_analysis" in sessions[req.session_id]:
                        community_msg = sessions[req.session_id]["community_analysis"]
                        community_data = {
                            "location": community_msg.location,
                            "overall_score": community_msg.overall_score,
                            "overall_explanation": community_msg.overall_explanation,
                            "safety_score": community_msg.safety_score,
                            "positive_stories": community_msg.positive_stories,
                            "negative_stories": community_msg.negative_stories,
                            "school_rating": community_msg.school_rating,
                            "school_explanation": community_msg.school_explanation,
                            "housing_price_per_square_foot": community_msg.housing_price_per_square_foot,
                            "average_house_size_square_foot": community_msg.average_house_size_square_foot
                        }

                    return ChatResponse(
                        status="success",
                        data={
                            "requirements": scoping_msg.requirements.dict(),
                            "properties": [p.dict() for p in research_msg.properties],
                            "search_summary": research_msg.search_summary,
                            "total_found": research_msg.total_found,
                            "top_result_coordinates": top_result_coords,
                            "raw_search_results": enhanced_results,
                            "community_analysis": community_data
                        }
                    )

            # Return scoping conversation (only if not searching)
            if scoping_msg.is_complete and scoping_msg.requirements:
                # Should have returned research results above - something went wrong
                return ChatResponse(
                    status="error",
                    data={"message": "Research agent did not respond in time"}
                )

            return ChatResponse(
                status="success",
                data={
                    "requirements": scoping_msg.requirements.dict() if scoping_msg.requirements else {},
                    "properties": [],
                    "search_summary": scoping_msg.agent_message,
                    "total_found": 0
                }
            )

        except Exception as e:
            ctx.logger.error(f"Error: {e}")
            import traceback
            traceback.print_exc()
            return ChatResponse(
                status="error",
                data={"message": str(e)}
            )

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
    print(f"   - REST API: http://localhost:8080/api/chat")
    print(f"   - Scoping: {scoping_address}")
    print(f"   - Research: {research_address}")
    print(f"   - General: {general_address}")
    print(f"   - Mapbox: {mapbox_address}")
    print(f"   - Local Discovery: {local_discovery_address}")
    print(f"   - Community Analysis: {community_analysis_address}")
    print("=" * 60)

    bureau.run()


if __name__ == "__main__":
    main()
