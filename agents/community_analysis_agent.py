from datetime import datetime
from uuid import uuid4
import os
import time
from typing import Dict, Any
import json

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
from tavily import TavilyClient

load_dotenv()
 
 
### Community News Finder Agent

## This agent analyzes community news for a given location and provides:
## - 2 positive news stories
## - 2 negative news stories
## - A community safety score (0-10 with precision to tenths)
## Returns structured JSON format for easy parsing

# REST API Models
class LocationNewsRequest(Model):
    location_name: str

class LocationNewsResponse(Model):
    timestamp: int
    location: str
    overall_score: float
    overall_explanation: str
    safety_score: float
    positive_stories: list  # List of dicts: [{"title": str, "summary": str, "url": str}, ...]
    negative_stories: list  # List of dicts: [{"title": str, "summary": str, "url": str}, ...]
    school_rating: float
    school_explanation: str
    housing_price_per_square_foot: int
    average_house_size_square_foot: int
    agent_address: str

# Model configuration
MODEL_NAME = "asi1-mini"

client = OpenAI(
    # By default, we are using the ASI:One LLM endpoint and model
    base_url='https://api.asi1.ai/v1',

    # You can get an ASI:One api key by creating an account at https://asi1.ai/dashboard/api-keys
    api_key=os.getenv('FETCH_AI_API_KEY'),
)

# Initialize Tavily client for real news search
tavily_client = TavilyClient(api_key=os.getenv('TAVILY_API_KEY'))

# Helper function to fetch real news articles using Tavily
def fetch_news_articles(location_name: str) -> list:
    """Fetch real news articles about a location using Tavily search."""
    try:
        # Search for recent news about the location
        search_query = f"{location_name} local news community safety crime development"
        response = tavily_client.search(
            query=search_query,
            max_results=20,
            search_depth="advanced",
            include_domains=[],
            exclude_domains=[]
        )

        articles = []
        if response and 'results' in response:
            for result in response['results']:
                articles.append({
                    'title': result.get('title', ''),
                    'url': result.get('url', ''),
                    'content': result.get('content', ''),
                    'score': result.get('score', 0)
                })

        return articles
    except Exception as e:
        print(f"Error fetching news articles: {e}")
        return []

# Helper function to fetch school-related articles using Tavily
def fetch_school_articles(location_name: str) -> list:
    """Fetch articles about schools and education in a location using Tavily search."""
    try:
        # Search for school ratings, rankings, and education quality
        search_query = f"{location_name} schools ratings rankings education quality greatschools niche"
        response = tavily_client.search(
            query=search_query,
            max_results=15,
            search_depth="advanced",
            include_domains=[],
            exclude_domains=[]
        )

        articles = []
        if response and 'results' in response:
            for result in response['results']:
                articles.append({
                    'title': result.get('title', ''),
                    'url': result.get('url', ''),
                    'content': result.get('content', ''),
                    'score': result.get('score', 0)
                })

        return articles
    except Exception as e:
        print(f"Error fetching school articles: {e}")
        return []

# Helper function to fetch housing data using Tavily
def fetch_housing_data(location_name: str) -> list:
    """Fetch articles about housing prices and market data in a location using Tavily search."""
    try:
        # Search for housing prices, market data, and real estate information
        search_query = f"{location_name} housing prices per square foot average home size zillow redfin realtor"
        response = tavily_client.search(
            query=search_query,
            max_results=15,
            search_depth="advanced",
            include_domains=[],
            exclude_domains=[]
        )

        articles = []
        if response and 'results' in response:
            for result in response['results']:
                articles.append({
                    'title': result.get('title', ''),
                    'url': result.get('url', ''),
                    'content': result.get('content', ''),
                    'score': result.get('score', 0)
                })

        return articles
    except Exception as e:
        print(f"Error fetching housing data: {e}")
        return []

# Helper function to query the model
def query_model(location_name: str) -> str:
    """Query the ASI:One model to get community news and safety analysis for a location."""
    try:
        # Fetch real news articles using Tavily
        articles = fetch_news_articles(location_name)
        # Fetch school-related articles
        school_articles = fetch_school_articles(location_name)
        # Fetch housing data articles
        housing_articles = fetch_housing_data(location_name)

        # Format the articles for the LLM
        articles_text = ""
        if articles:
            articles_text = "Here are recent news articles about this location:\n\n"
            for i, article in enumerate(articles, 1):
                articles_text += f"{i}. {article['title']}\n"
                articles_text += f"   Content: {article['content'][:300]}...\n"
                articles_text += f"   URL: {article['url']}\n\n"
        else:
            articles_text = "No recent news articles found. Please provide a general analysis based on your knowledge.\n\n"

        # Format school articles for the LLM
        school_text = ""
        if school_articles:
            school_text = "Here are articles about schools and education in this location:\n\n"
            for i, article in enumerate(school_articles, 1):
                school_text += f"{i}. {article['title']}\n"
                school_text += f"   Content: {article['content'][:300]}...\n"
                school_text += f"   URL: {article['url']}\n\n"
        else:
            school_text = "No school-related articles found. Please provide a general school rating based on your knowledge.\n\n"

        # Format housing articles for the LLM
        housing_text = ""
        if housing_articles:
            housing_text = "Here are articles about housing and real estate in this location:\n\n"
            for i, article in enumerate(housing_articles, 1):
                housing_text += f"{i}. {article['title']}\n"
                housing_text += f"   Content: {article['content'][:300]}...\n"
                housing_text += f"   URL: {article['url']}\n\n"
        else:
            housing_text = "No housing-related articles found. Please provide general housing estimates based on your knowledge.\n\n"

        r = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": """
You are a community news analyst. You will be given real news articles about a location, and you need to analyze them.
You MUST respond with ONLY valid JSON in the following format (no additional text):

{
  "location": "location name",
  "overall": {
    "score": 7.9,
    "explanation": "Brief explanation of overall rating"
  },
  "safety": {
    "score": 7.5,
    "positive_stories": [
      {"title": "story title 1", "summary": "brief summary", "url": "article url"},
      {"title": "story title 2", "summary": "brief summary", "url": "article url"}
    ],
    "negative_stories": [
      {"title": "story title 1", "summary": "brief summary", "url": "article url"},
      {"title": "story title 2", "summary": "brief summary", "url": "article url"}
    ]
  },
  "schools": {
    "score": 8.2,
    "explanation": "Brief explanation of school rating based on the education articles"
  },
  "housing_avg": {
    "housing_price_per_square_foot": 739,
    "average_house_size_square_foot": 1921
  }
}

FOLLOW THESE INSTRUCTIONS STRICTLY:
- All scores (overall, safety, schools) must be numbers from 0-10 with precision to tenths (e.g., 7.3, 8.5).
- The overall score should be calculated as the average of safety and schools scores.
- Analyze the provided news articles and categorize them into positive and negative stories under the safety section.
- The included url links to the real news articles.
- Choose the 2 most relevant positive stories and 2 most relevant negative stories for safety.
- Base your safety score on the content of the articles, crime reports, community development news, and quality of life indicators.
- Base your schools score on school quality indicators, ratings from sources like GreatSchools or Niche, test scores, and education-related news.
- Extract housing_price_per_square_foot and average_house_size_square_foot from the housing articles (as integer values).
- If housing data cannot be found in the articles, provide reasonable estimates based on your knowledge of the area.

YOU WILL CHOOSE THE NEWS ARTICLES THAT YOU INCLUDE ACCORDING TO THE FOLLOWING CRITERIA (LISTED IN ORDER OF IMPORTANCE):
- Choose sources that are specific news articles about the location, not generic news websites.
- Choose sources that are relevant and informative to the location.
- Choose sources that are most recent.
                """},
                {"role": "user", "content": f"Analyze community news and safety for: {location_name}\n\n{articles_text}\n{school_text}\n{housing_text}"},
            ],
            max_tokens=2048,
        )
        return str(r.choices[0].message.content)
    except Exception as e:
        raise e

agent = Agent(
    name="Community Analysis Agent",
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

    # collect up all the text chunks (expecting a location name)
    location_name = ''
    for item in msg.content:
        if isinstance(item, TextContent):
            location_name += item.text

    # query the model for community news analysis
    response = 'I am afraid something went wrong and I am unable to analyze the community news at the moment'
    try:
        response = query_model(location_name.strip())
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

@agent.on_rest_get("/status", LocationNewsResponse)
async def handle_status(ctx: Context) -> Dict[str, Any]:
    """GET endpoint to check agent status"""
    return {
        "timestamp": int(time.time()),
        "location": "N/A",
        "overall_score": 0.0,
        "overall_explanation": "N/A",
        "safety_score": 0.0,
        "positive_stories": [],
        "negative_stories": [],
        "school_rating": 0.0,
        "school_explanation": "N/A",
        "housing_price_per_square_foot": 0,
        "average_house_size_square_foot": 0,
        "agent_address": ctx.agent.address,
        "status": f"Community news agent is running",
    }

@agent.on_rest_post("/ask", LocationNewsRequest, LocationNewsResponse)
async def handle_analyze(ctx: Context, req: LocationNewsRequest) -> LocationNewsResponse:
    """POST endpoint to analyze community news for a location"""
    import json

    ctx.logger.info(f"Received location analysis request via REST API: {req.location_name}")

    # Query the model with the location name
    try:
        response_text = query_model(req.location_name)
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

        # Extract nested data
        overall_data = response_data.get("overall", {})
        safety_data = response_data.get("safety", {})
        schools_data = response_data.get("schools", {})
        housing_data = response_data.get("housing_avg", {})

        return LocationNewsResponse(
            timestamp=int(time.time()),
            location=response_data.get("location", req.location_name),
            overall_score=float(overall_data.get("score", 0.0)),
            overall_explanation=overall_data.get("explanation", "N/A"),
            safety_score=float(safety_data.get("score", 0.0)),
            positive_stories=safety_data.get("positive_stories", []),
            negative_stories=safety_data.get("negative_stories", []),
            school_rating=float(schools_data.get("score", 0.0)),
            school_explanation=schools_data.get("explanation", "N/A"),
            housing_price_per_square_foot=int(housing_data.get("housing_price_per_square_foot", 0)),
            average_house_size_square_foot=int(housing_data.get("average_house_size_square_foot", 0)),
            agent_address=ctx.agent.address,
        )
    except json.JSONDecodeError as e:
        ctx.logger.exception(f'Error parsing JSON response: {e}')
        return LocationNewsResponse(
            timestamp=int(time.time()),
            location=req.location_name,
            overall_score=0.0,
            overall_explanation="Error parsing response",
            safety_score=0.0,
            positive_stories=[],
            negative_stories=[],
            school_rating=0.0,
            school_explanation="Error parsing response",
            housing_price_per_square_foot=0,
            average_house_size_square_foot=0,
            agent_address=ctx.agent.address,
        )
    except Exception as e:
        ctx.logger.exception(f'Error querying model: {e}')
        return LocationNewsResponse(
            timestamp=int(time.time()),
            location=req.location_name,
            overall_score=0.0,
            overall_explanation="Error querying model",
            safety_score=0.0,
            positive_stories=[],
            negative_stories=[],
            school_rating=0.0,
            school_explanation="Error querying model",
            housing_price_per_square_foot=0,
            average_house_size_square_foot=0,
            agent_address=ctx.agent.address,
        )


if __name__ == "__main__":
    agent.run()
