"""
Shared Models for Estate uAgents System
=======================================

This file contains all the uAgents models used across the system.
"""

from __future__ import annotations
from typing import List, Optional
from uagents import Model


# Base Models (defined first to avoid forward references)
class UserRequirements(Model):
    """Structured user requirements after scoping is complete"""
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    location: str
    additional_info: Optional[str] = None


class PropertyListing(Model):
    """Individual property listing"""
    address: str
    city: str
    price: Optional[int] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    sqft: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    description: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None  # Property image URL


# Scoping Agent Models
class ScopingRequest(Model):
    """Request to start scoping conversation with user"""
    user_message: str
    session_id: str


class ScopingResponse(Model):
    """Response from scoping agent"""
    agent_message: str
    is_complete: bool
    session_id: str
    requirements: Optional[UserRequirements] = None
    is_general_question: bool = False
    general_question: Optional[str] = None
    community_name: Optional[str] = None  # Location/community for analysis


# Research Agent Models
class ResearchRequest(Model):
    """Request to research agent to find properties"""
    requirements: UserRequirements
    session_id: str


class ResearchResponse(Model):
    """Response from research agent with property listings"""
    properties: List[PropertyListing]
    search_summary: str
    total_found: int
    session_id: str
    raw_search_results: Optional[List[dict]] = None  # Raw organic search results from BrightData
    top_result_image_url: Optional[str] = None  # Image URL of top result (legacy)
    result_images: Optional[List[dict]] = None  # List of {"index": int, "image_url": str} for all results


# General Agent Models
class GeneralRequest(Model):
    """Request to general agent for information"""
    question: str
    session_id: str


class GeneralResponse(Model):
    """Response from general agent"""
    answer: str
    session_id: str


# Mapbox Agent Models
class MapboxRequest(Model):
    """Request to Mapbox agent to geocode address"""
    address: str
    session_id: str


class MapboxResponse(Model):
    """Response from Mapbox agent with coordinates"""
    address: str
    latitude: float
    longitude: float
    session_id: str
    error: Optional[str] = None
    image_url: Optional[str] = None  # Property image from scraping


# Local Discovery Agent Models
class POI(Model):
    """Point of Interest near a property"""
    name: str
    category: str
    latitude: float
    longitude: float
    address: Optional[str] = None
    distance_meters: Optional[int] = None


class LocalDiscoveryRequest(Model):
    """Request to find POIs near a location"""
    latitude: float
    longitude: float
    session_id: str
    listing_index: int  # Which listing (0-4)


class LocalDiscoveryResponse(Model):
    """Response with POIs near a location"""
    pois: List[POI]
    session_id: str
    listing_index: int


# Community Analysis Agent Models
class CommunityAnalysisRequest(Model):
    """Request to analyze community news and metrics"""
    location_name: str
    session_id: str


class CommunityAnalysisResponse(Model):
    """Response with community analysis metrics"""
    location: str
    overall_score: float
    overall_explanation: str
    safety_score: float
    positive_stories: List[dict]  # [{"title": str, "summary": str, "url": str}, ...]
    negative_stories: List[dict]  # [{"title": str, "summary": str, "url": str}, ...]
    school_rating: float
    school_explanation: str
    housing_price_per_square_foot: int
    average_house_size_square_foot: int
    session_id: str


# Final Result Model
class EstateSearchResult(Model):
    """Complete result of the estate search process"""
    requirements: UserRequirements
    properties: List[PropertyListing]
    search_summary: str
    session_id: str
