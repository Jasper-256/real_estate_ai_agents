"""
Mapbox Agent - Geocodes addresses to coordinates using Mapbox Geocoding API
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
import aiohttp
import os
from dotenv import load_dotenv
load_dotenv()

mapbox_token = os.getenv("MAPBOX_API_KEY")

def create_text_chat(text: str, end_session: bool = False) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(timestamp=datetime.utcnow(), msg_id=uuid4(), content=content)


async def geocode_address(address: str) -> dict:
    """
    Use Mapbox Geocoding API to convert address to coordinates.
    Returns dict with latitude, longitude, or error
    """
    if not mapbox_token:
        return {"error": "Mapbox token not configured"}

    # Mapbox Geocoding API endpoint
    url = f"https://api.mapbox.com/search/geocode/v6/forward"

    params = {
        "q": address,
        "access_token": mapbox_token,
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


agent = Agent(
    name="Mapbox Agent",
    seed="mapbox_agent_seed_12343325",
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

    ctx.logger.info(f"Geocoding address: {text}")

    try:
        result = await geocode_address(text)

        if "error" in result:
            ctx.logger.warning(f"Geocoding error: {result['error']}")
            response = f"Error: {result['error']}"
        else:
            ctx.logger.info(f"Geocoded to: {result['latitude']}, {result['longitude']}")
            response = f"Address: {result.get('full_address', text)}\nLatitude: {result['latitude']}\nLongitude: {result['longitude']}"

    except Exception as e:
        ctx.logger.exception('Error geocoding address')
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
