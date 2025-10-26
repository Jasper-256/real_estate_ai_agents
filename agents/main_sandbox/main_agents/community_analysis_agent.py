"""
Community Analysis Agent - Analyzes community news, safety, schools, and housing metrics
"""
import os
import json
from openai import OpenAI
from uagents import Agent, Context
from tavily import TavilyClient
from dotenv import load_dotenv
from .models import CommunityAnalysisRequest, CommunityAnalysisResponse

load_dotenv()


def create_community_analysis_agent(port: int = 8006):
    """Create and configure the community analysis agent"""

    agent = Agent(
        name="community_analysis_agent",
        port=port,
        seed="community_analysis_agent_seed",
        endpoint=[f"http://localhost:{port}/submit"]
    )

    # Model configuration
    MODEL_NAME = "asi1-mini"

    client = OpenAI(
        base_url='https://api.asi1.ai/v1',
        api_key=os.getenv('ASI_API_KEY'),
    )

    # Initialize Tavily client for real news search
    tavily_client = TavilyClient(api_key=os.getenv('TAVILY_API_KEY'))

    # Helper function to fetch real news articles using Tavily
    async def fetch_news_articles(location_name: str) -> list:
        """Fetch real news articles about a location using Tavily search."""
        try:
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
    async def fetch_school_articles(location_name: str) -> list:
        """Fetch articles about schools and education in a location using Tavily search."""
        try:
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
    async def fetch_housing_data(location_name: str) -> list:
        """Fetch articles about housing prices and market data in a location using Tavily search."""
        try:
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
    async def query_model(location_name: str) -> str:
        """Query the ASI:One model to get community news and safety analysis for a location."""
        try:
            # Fetch real news articles using Tavily
            articles = await fetch_news_articles(location_name)
            school_articles = await fetch_school_articles(location_name)
            housing_articles = await fetch_housing_data(location_name)

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

    @agent.on_event("startup")
    async def startup(ctx: Context):
        ctx.logger.info(f"Community Analysis Agent started at {ctx.agent.address}")

    @agent.on_message(model=CommunityAnalysisRequest)
    async def handle_request(ctx: Context, sender: str, msg: CommunityAnalysisRequest):
        ctx.logger.info(f"Community Analysis agent received request for location: {msg.location_name}")

        try:
            # Query the model with the location name
            response_text = await query_model(msg.location_name)
            ctx.logger.info(f"Generated response for {msg.location_name}")

            # Strip markdown code blocks if present
            cleaned_text = response_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            elif cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]

            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]

            cleaned_text = cleaned_text.strip()

            # Parse the JSON response
            response_data = json.loads(cleaned_text)

            # Extract nested data
            overall_data = response_data.get("overall", {})
            safety_data = response_data.get("safety", {})
            schools_data = response_data.get("schools", {})
            housing_data = response_data.get("housing_avg", {})

            response = CommunityAnalysisResponse(
                location=response_data.get("location", msg.location_name),
                overall_score=float(overall_data.get("score", 0.0)),
                overall_explanation=overall_data.get("explanation", "N/A"),
                safety_score=float(safety_data.get("score", 0.0)),
                positive_stories=safety_data.get("positive_stories", []),
                negative_stories=safety_data.get("negative_stories", []),
                school_rating=float(schools_data.get("score", 0.0)),
                school_explanation=schools_data.get("explanation", "N/A"),
                housing_price_per_square_foot=int(housing_data.get("housing_price_per_square_foot", 0)),
                average_house_size_square_foot=int(housing_data.get("average_house_size_square_foot", 0)),
                session_id=msg.session_id
            )

            await ctx.send(sender, response)

        except json.JSONDecodeError as e:
            ctx.logger.exception(f'Error parsing JSON response: {e}')
            response = CommunityAnalysisResponse(
                location=msg.location_name,
                overall_score=0.0,
                overall_explanation="Error parsing response",
                safety_score=0.0,
                positive_stories=[],
                negative_stories=[],
                school_rating=0.0,
                school_explanation="Error parsing response",
                housing_price_per_square_foot=0,
                average_house_size_square_foot=0,
                session_id=msg.session_id
            )
            await ctx.send(sender, response)

        except Exception as e:
            ctx.logger.exception(f'Error querying model: {e}')
            response = CommunityAnalysisResponse(
                location=msg.location_name,
                overall_score=0.0,
                overall_explanation="Error querying model",
                safety_score=0.0,
                positive_stories=[],
                negative_stories=[],
                school_rating=0.0,
                school_explanation="Error querying model",
                housing_price_per_square_foot=0,
                average_house_size_square_foot=0,
                session_id=msg.session_id
            )
            await ctx.send(sender, response)

    return agent
