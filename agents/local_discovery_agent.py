"""
Local Discovery Agent - Finds Points of Interest (POIs) near property listings using Mapbox
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
import aiohttp
import os
import json
from typing import List


def create_text_chat(text: str, end_session: bool = False) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(timestamp=datetime.utcnow(), msg_id=uuid4(), content=content)


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


agent = Agent(
    name="Local Discovery Agent",
    seed="local_discovery_agent_seed_1232233",
    mailbox=True,
)

# Create protocol compatible with chat protocol spec
protocol = Protocol(spec=chat_protocol_spec)


# Handler for chat messages
@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    # Send acknowledgement
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(), acknowledged_msg_id=msg.msg_id),
    )

    text = msg.text()
    if not text:
        return

    try:
        # Try to parse the input as JSON with latitude/longitude
        # Expected format: {"latitude": 37.7749, "longitude": -122.4194}
        data = json.loads(text)
        latitude = float(data.get("latitude"))
        longitude = float(data.get("longitude"))

        ctx.logger.info(f"Finding POIs near ({latitude}, {longitude})")

        # Search for POIs near this location
        poi_data = await search_pois_near_location(latitude, longitude, limit_per_category=2)

        ctx.logger.info(f"Found {len(poi_data)} POIs")

        # Format response
        if poi_data:
            response = f"Found {len(poi_data)} points of interest near ({latitude}, {longitude}):\n\n"
            for poi in poi_data:
                distance = f" ({poi['distance_meters']}m away)" if poi.get('distance_meters') else ""
                response += f"• {poi['name']} ({poi['category']}){distance}\n"
                if poi.get('address'):
                    response += f"  {poi['address']}\n"
        else:
            response = f"No points of interest found near ({latitude}, {longitude})."

    except json.JSONDecodeError:
        response = "Please provide location in JSON format: {\"latitude\": 37.7749, \"longitude\": -122.4194}"
    except (KeyError, ValueError, TypeError) as e:
        ctx.logger.exception('Error parsing location')
        response = f"Invalid location data. Please provide valid latitude and longitude values. Error: {e}"
    except Exception as e:
        ctx.logger.exception('Error finding POIs')
        response = f"An error occurred while searching for points of interest. Please try again later. {e}"

    await ctx.send(sender, create_text_chat(response, end_session=True))


@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    # Not processing acknowledgements in this example
    pass


# Attach protocol to agent
agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
