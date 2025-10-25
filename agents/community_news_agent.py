from datetime import datetime
from uuid import uuid4
import os
import time
from typing import Dict, Any

from openai import OpenAI
from uagents import Context, Protocol, Agent, Model
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)
from dotenv import load_dotenv
load_dotenv()
 
 
### Community News Finder Agent

## This agent analyzes community news for a given city and provides:
## - 2 positive news stories
## - 2 negative news stories
## - A community safety score (0-10 with precision to tenths)
## Returns structured JSON format for easy parsing

# REST API Models
class CityNewsRequest(Model):
    city_name: str

class CityNewsResponse(Model):
    timestamp: int
    city: str
    positive_stories: list
    negative_stories: list
    safety_score: float
    agent_address: str

# the subject that this assistant is an expert in
subject_matter = "community news and safety analysis"

# Model configuration
MODEL_NAME = "asi1-mini"

client = OpenAI(
    # By default, we are using the ASI:One LLM endpoint and model
    base_url='https://api.asi1.ai/v1',

    # You can get an ASI:One api key by creating an account at https://asi1.ai/dashboard/api-keys
    api_key=os.getenv('FETCH_AI_API_KEY'),
)

# Helper function to query the model
def query_model(city_name: str) -> str:
    """Query the ASI:One model to get community news and safety analysis for a city."""
    try:
        r = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": """
You are a community news analyst. When given a city name, you analyze recent news and community safety.
You MUST respond with ONLY valid JSON in the following format (no additional text):

{
  "city": "city name",
  "positive_stories": [
    {"title": "story title 1", "summary": "brief summary"},
    {"title": "story title 2", "summary": "brief summary"}
  ],
  "negative_stories": [
    {"title": "story title 1", "summary": "brief summary"},
    {"title": "story title 2", "summary": "brief summary"}
  ],
  "safety_score": 7.5,
  "safety_explanation": "Brief explanation of safety score"
}

The safety_score must be a number from 0-10 with precision to tenths (e.g., 7.3, 8.5).
Base your analysis on typical news patterns, crime statistics, community development, and quality of life indicators for the city.
                """},
                {"role": "user", "content": f"Analyze community news and safety for: {city_name}"},
            ],
            max_tokens=2048,
        )
        return str(r.choices[0].message.content)
    except Exception as e:
        raise e

agent = Agent(
    name="community-news-agent",
    seed="8792459787894231",
    port=8001,
    endpoint=["http://localhost:8001/submit"],
    mailbox=True,
    publish_agent_details=True,
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

    # collect up all the text chunks (expecting a city name)
    city_name = ''
    for item in msg.content:
        if isinstance(item, TextContent):
            city_name += item.text

    # query the model for community news analysis
    response = 'I am afraid something went wrong and I am unable to analyze the community news at the moment'
    try:
        response = query_model(city_name.strip())
    except:
        ctx.logger.exception('Error querying model')

    # send the response back to the user
    await ctx.send(sender, ChatMessage(
        timestamp=datetime.now(),
        msg_id=uuid4(),
        content=[
            # we send the contents back in the chat message
            TextContent(type="text", text=response),
            # we also signal that the session is over, this also informs the user that we are not recording any of the
            # previous history of messages.
            EndSessionContent(type="end-session"),
        ]
    ))



@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    # we are not interested in the acknowledgements for this example, but they can be useful to
    # implement read receipts, for example.
    pass
 
 
# attach the protocol to the agent
agent.include(protocol, publish_manifest=True)


# REST API Endpoints

@agent.on_rest_get("/status", CityNewsResponse)
async def handle_status(ctx: Context) -> Dict[str, Any]:
    """GET endpoint to check agent status"""
    return {
        "timestamp": int(time.time()),
        "city": "N/A",
        "positive_stories": [],
        "negative_stories": [],
        "safety_score": 0.0,
        "agent_address": ctx.agent.address,
        "status": f"Community news agent is running and ready to analyze {subject_matter}",
    }

@agent.on_rest_post("/ask", CityNewsRequest, CityNewsResponse)
async def handle_analyze(ctx: Context, req: CityNewsRequest) -> CityNewsResponse:
    """POST endpoint to analyze community news for a city"""
    import json

    ctx.logger.info(f"Received city analysis request via REST API: {req.city_name}")

    # Query the model with the city name
    try:
        response_text = query_model(req.city_name)
        ctx.logger.info(f"Generated response: {response_text}")

        # Strip markdown code blocks if present
        cleaned_text = response_text.strip()
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:]  # Remove ```json
        elif cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:]  # Remove ```

        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3]  # Remove closing ```

        cleaned_text = cleaned_text.strip()

        # Parse the JSON response
        response_data = json.loads(cleaned_text)

        return CityNewsResponse(
            timestamp=int(time.time()),
            city=response_data.get("city", req.city_name),
            positive_stories=response_data.get("positive_stories", []),
            negative_stories=response_data.get("negative_stories", []),
            safety_score=float(response_data.get("safety_score", 0.0)),
            agent_address=ctx.agent.address,
        )
    except json.JSONDecodeError as e:
        ctx.logger.exception(f'Error parsing JSON response: {e}')
        return CityNewsResponse(
            timestamp=int(time.time()),
            city=req.city_name,
            positive_stories=[],
            negative_stories=[],
            safety_score=0.0,
            agent_address=ctx.agent.address,
        )
    except Exception as e:
        ctx.logger.exception(f'Error querying model: {e}')
        return CityNewsResponse(
            timestamp=int(time.time()),
            city=req.city_name,
            positive_stories=[],
            negative_stories=[],
            safety_score=0.0,
            agent_address=ctx.agent.address,
        )


if __name__ == "__main__":
    agent.run()
