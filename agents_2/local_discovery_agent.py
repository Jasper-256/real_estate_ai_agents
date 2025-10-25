"""
Local Discovery Agent - Finds Points of Interest (POIs) near property listings using Mapbox
"""
from uagents import Agent, Context
from .models import LocalDiscoveryRequest, LocalDiscoveryResponse, POI
import aiohttp
import os
from typing import List


MAPBOX_TOKEN = os.getenv("MAPBOX_API_KEY")

# POI categories to search for near each listing
POI_CATEGORIES = [
    "school",
    "hospital",
    "grocery",
    "restaurant",
    "park",
    "transit_station",
    "cafe",
    "gym"
]


async def search_pois_near_location(latitude: float, longitude: float, limit_per_category: int = 2) -> List[dict]:
    """
    Search for POIs near a location using Mapbox Search Box API.
    Returns a list of POIs with name, category, coordinates, address, distance.
    """
    if not MAPBOX_TOKEN:
        return []

    all_pois = []

    for category in POI_CATEGORIES:
        url = f"https://api.mapbox.com/search/searchbox/v1/category/{category}"

        params = {
            "access_token": MAPBOX_TOKEN,
            "proximity": f"{longitude},{latitude}",  # Mapbox uses lon,lat order
            "limit": limit_per_category,
            "language": "en"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        continue  # Skip this category on error

                    data = await resp.json()

                    # Parse features from response
                    for feature in data.get("features", []):
                        properties = feature.get("properties", {})
                        geometry = feature.get("geometry", {})
                        coords = geometry.get("coordinates", [])

                        if len(coords) >= 2:
                            poi = {
                                "name": properties.get("name", "Unknown"),
                                "category": category,
                                "latitude": coords[1],  # GeoJSON is [lon, lat]
                                "longitude": coords[0],
                                "address": properties.get("full_address", properties.get("place_formatted", "")),
                                "distance_meters": properties.get("distance")
                            }
                            all_pois.append(poi)

        except Exception as e:
            print(f"Error searching {category}: {e}")
            continue

    return all_pois


def create_local_discovery_agent(port: int = 8005):
    agent = Agent(
        name="local_discovery_agent",
        port=port,
        seed="local_discovery_agent_seed",
        endpoint=[f"http://localhost:{port}/submit"],
    )

    @agent.on_event("startup")
    async def startup(ctx: Context):
        ctx.logger.info(f"Local Discovery Agent started at {ctx.agent.address}")

    @agent.on_message(model=LocalDiscoveryRequest)
    async def handle_discovery_request(ctx: Context, sender: str, msg: LocalDiscoveryRequest):
        ctx.logger.info(f"Finding POIs near ({msg.latitude}, {msg.longitude}) for listing {msg.listing_index}")

        # Search for POIs near this location
        poi_data = await search_pois_near_location(msg.latitude, msg.longitude, limit_per_category=2)

        ctx.logger.info(f"Found {len(poi_data)} POIs for listing {msg.listing_index}")

        # Convert to POI models
        pois = []
        for poi_dict in poi_data:
            try:
                pois.append(POI(
                    name=poi_dict["name"],
                    category=poi_dict["category"],
                    latitude=poi_dict["latitude"],
                    longitude=poi_dict["longitude"],
                    address=poi_dict.get("address"),
                    distance_meters=poi_dict.get("distance_meters")
                ))
            except Exception as e:
                ctx.logger.warning(f"Failed to create POI model: {e}")
                continue

        # Send response back
        await ctx.send(sender, LocalDiscoveryResponse(
            pois=pois,
            session_id=msg.session_id,
            listing_index=msg.listing_index
        ))

    return agent
