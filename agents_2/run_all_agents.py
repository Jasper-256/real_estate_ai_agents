from scoping_agent import agent as scoping_agent
from community_analysis_agent import agent as community_analysis_agent
from real_estate_intern import agent as real_estate_intern
from local_discovery_agent import agent as local_discovery_agent
from mapbox_agent import agent as mapbox_agent
from research_agent import agent as research_agent

if __name__ == "__main__":
    scoping_agent.run()
    community_analysis_agent.run()
    real_estate_intern.run()
    local_discovery_agent.run()
    mapbox_agent.run()
    research_agent.run()
