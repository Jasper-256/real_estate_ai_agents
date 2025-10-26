"""
Tavily Client for Research Agent
=================================

This module provides async Tavily search functionality for the research agent.
"""

import os
from typing import List, Dict, Any
from dotenv import load_dotenv
import aiohttp

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TAVILY_API_URL = "https://api.tavily.com/search"


class TavilyClient:
    """Async client for Tavily search API"""

    def __init__(self):
        self.api_key = TAVILY_API_KEY
        self.api_url = TAVILY_API_URL

    async def search(
        self,
        query: str,
        search_depth: str = "advanced",
        max_results: int = 10,
        include_domains: List[str] = None,
        exclude_domains: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Perform a Tavily search

        Args:
            query: Search query string
            search_depth: 'basic' or 'advanced'
            max_results: Maximum number of results to return
            include_domains: List of domains to include
            exclude_domains: List of domains to exclude

        Returns:
            Dict containing search results
        """

        if not self.api_key:
            return {
                "success": False,
                "error": "TAVILY_API_KEY not configured in environment variables",
                "results": []
            }

        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_answer": True,
            "include_raw_content": False,
        }

        if include_domains:
            payload["include_domains"] = include_domains

        if exclude_domains:
            payload["exclude_domains"] = exclude_domains

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "success": True,
                            "results": data.get("results", []),
                            "answer": data.get("answer", ""),
                            "query": query
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": f"Tavily API error {response.status}: {error_text}",
                            "results": []
                        }
        except Exception as e:
            return {
                "success": False,
                "error": f"Tavily search error: {str(e)}",
                "results": []
            }
