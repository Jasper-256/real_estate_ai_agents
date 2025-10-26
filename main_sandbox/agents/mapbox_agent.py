"""
Mapbox Agent - Geocodes addresses to coordinates using Mapbox Geocoding API
"""
from uagents import Agent, Context
from .models import MapboxRequest, MapboxResponse
import aiohttp
import os


MAPBOX_TOKEN = os.getenv("MAPBOX_API_KEY")


async def geocode_address(address: str) -> dict:
    """
    Use Mapbox Geocoding API to convert address to coordinates.
    Returns dict with latitude, longitude, or error
    """
    if not MAPBOX_TOKEN:
        return {"error": "Mapbox token not configured"}

    # Mapbox Geocoding API endpoint
    url = f"https://api.mapbox.com/search/geocode/v6/forward"

    params = {
        "q": address,
        "access_token": MAPBOX_TOKEN,
        "limit": 1,  # Only get top result
        "country": "US"  # Restrict to US addresses
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    return {"error": f"Mapbox API error {resp.status}: {text}"}

                data = await resp.json()

                # Extract coordinates from response
                if data.get("features") and len(data["features"]) > 0:
                    feature = data["features"][0]
                    coords = feature["geometry"]["coordinates"]

                    return {
                        "latitude": coords[1],  # Mapbox returns [lng, lat]
                        "longitude": coords[0],
                        "full_address": feature["properties"].get("full_address", address)
                    }
                else:
                    return {"error": "No coordinates found for address"}

    except Exception as e:
        return {"error": f"Geocoding failed: {str(e)}"}


def create_mapbox_agent(port: int = 8004):
    agent = Agent(
        name="mapbox_agent",
        port=port,
        seed="mapbox_agent_seed",
        endpoint=[f"http://localhost:{port}/submit"],
    )

    @agent.on_event("startup")
    async def startup(ctx: Context):
        ctx.logger.info(f"Mapbox Agent started at {ctx.agent.address}")

    @agent.on_message(model=MapboxRequest)
    async def handle_geocode_request(ctx: Context, sender: str, msg: MapboxRequest):
        ctx.logger.info(f"Geocoding address: {msg.address}")

        result = await geocode_address(msg.address)

        if "error" in result:
            ctx.logger.warning(f"Geocoding error: {result['error']}")
            await ctx.send(sender, MapboxResponse(
                address=msg.address,
                latitude=0.0,
                longitude=0.0,
                session_id=msg.session_id,
                error=result["error"]
            ))
        else:
            ctx.logger.info(f"Geocoded to: {result['latitude']}, {result['longitude']}")
            await ctx.send(sender, MapboxResponse(
                address=result.get("full_address", msg.address),
                latitude=result["latitude"],
                longitude=result["longitude"],
                session_id=msg.session_id
            ))

    return agent
