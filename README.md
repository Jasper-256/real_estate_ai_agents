![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

# Real Estate AI Agents

A multi-agent system for intelligent real estate property search and analysis across the United States.

## Deployed Agents on Agentverse

- [Real Estate Agent (Coordinator)](https://agentverse.ai/agents/details/agent1qg0lmv734dqg402qsrma08jvepjqgpf3krz733nsckstptr3e9a82haqldl/profile)
- [Scoping Agent](https://agentverse.ai/agents/details/agent1qtuv3paxfpc7r44x5xxhttlgurtm7rkdf97z0dgfr34r8gf0zp0asyhtnse/profile)
- [Community Analysis Agent](https://agentverse.ai/agents/details/agent1q2d44gnyd9rfm4dwxaje96v8q3m30nhckpwkn5zte38ecn6y8k6vyjavunw/profile)
- [Real Estate Intern](https://agentverse.ai/agents/details/agent1qv5xsu3s92n8wxe2zq0gx425jsfxcyz3aeedtntp7f45argyturk6m0ez45/profile)
- [Local Discovery Agent](https://agentverse.ai/agents/details/agent1q0a0ctl6xt9pqgawtvts9m3p9fn0hhxhd4zm5l2a4r2twqqsssk45zjypfq/profile)
- [Mapbox Agent](https://agentverse.ai/agents/details/agent1qfwz4lx0rj2a7dsak4wswmnanql8u9yk9dvf97jy73z8vh5yknh6z0ncn2y/profile)
- [Research Agent](https://agentverse.ai/agents/details/agent1qd6snf9k3kd68djglmfzd9kcjnjtv43gn7dpnt9zj4ta6w2n9fyfvj09hmh/profile)
- [Prober Agent](https://agentverse.ai/agents/details/agent1qvrd39sql7fw6pz4kz7eq0gus8q5sup90x8h0zddyq4063vyh4v6z90vnys/profile)
- [Vapi Negotiator](https://agentverse.ai/agents/details/agent1qf94mszakc8gj3qq9nyfwc5gn7hne48kld2crzqfag0y0xu3jfjy6hkfxaw/profile)

## Core Agents

### Real Estate Agent (Coordinator)
Orchestrates the entire workflow by routing messages between agents, managing session state, collecting geocoded data for multiple properties, generating static map images with numbered markers, and assembling comprehensive final responses with all property details.

### Scoping Agent
Conversationally collects user requirements for property search including budget range, bedrooms, bathrooms, and location. Routes requests to appropriate agents based on whether user is asking general questions or searching for properties.

### Research Agent
Searches for property listings using BrightData's search engine API. Generates AI-powered summaries of available properties, scrapes listing images from Redfin/Zillow, and returns structured property data with links.

### Real Estate Intern
Handles general questions about neighborhoods, schools, amenities, and local information. Uses Tavily search to gather current information and ASI-1 LLM to provide conversational, helpful answers.

### Mapbox Agent
Geocodes property addresses to latitude/longitude coordinates using Mapbox Geocoding API. Enables map visualization and location-based features.

### Local Discovery Agent
Finds Points of Interest (POIs) near properties using Mapbox Search Box API. Discovers nearby schools, hospitals, grocery stores, restaurants, parks, transit stations, cafes, and gyms.

### Community Analysis Agent
Analyzes community quality using Tavily search to gather news articles, school ratings, and housing data. Provides scores for overall quality, safety, and schools (0-10 scale), along with positive/negative news stories, housing price per sqft, and average house size.

### Prober Agent
Gathers intelligence about properties for negotiation leverage by identifying red flags, weaknesses, and negative information. Uses Tavily to search property history and BrightData to scrape detailed content. Analyzes time on market, price reductions, property issues, owner situations, and market conditions to generate a leverage score and actionable findings for buyers to negotiate lower prices.

### Vapi Negotiator
Handles AI phone call negotiations with listing agents on behalf of buyers. Makes actual phone calls using the Vapi platform to negotiate property prices based on intelligence gathered by the Prober Agent. Uses a strategic system prompt with negotiation tactics, maintains professional conversation, and provides call summaries with outcomes.

## Supporting Components

### General Agent
Alternative implementation in main_sandbox that answers general real estate questions using Tavily search and LLM analysis.

### Utility Clients
- **brightdata_client.py** - Interface to BrightData for web scraping and search
- **tavily_client.py** - Interface to Tavily for advanced web search
- **llm_client.py** - Simplified wrapper for ASI-1 LLM interactions
- **models.py** - Pydantic data models for inter-agent communication

## Running the System

### Full System
```bash
python agents/main_sandbox/main.py
```
Runs the complete multi-agent system with coordinator on port 8080.

### Individual Agents
```bash
python agents/run_all_agents.py
```
Runs all agents concurrently in a Bureau.

### Single Agent
Run any agent individually:
```bash
python agents/scoping_agent.py
python agents/research_agent.py
# etc.
```

## Architecture

The system uses a hub-and-spoke pattern where the Coordinator Agent receives user messages via chat protocol, delegates to specialized agents (scoping, research, mapbox, community analysis, local discovery), and aggregates results into a comprehensive property search response with maps, images, and community insights.

## APIs Used
- **ASI-1** - Large language model for conversational AI
- **BrightData** - Web scraping and search engine access
- **Tavily** - Advanced web search for news and data
- **Mapbox** - Geocoding, static maps, and POI discovery
