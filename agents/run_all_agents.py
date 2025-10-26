from uagents import Bureau
from scoping_agent import agent as scoping_agent
from community_analysis_agent import agent as community_analysis_agent
from real_estate_intern import agent as real_estate_intern
from local_discovery_agent import agent as local_discovery_agent
from mapbox_agent import agent as mapbox_agent
from research_agent import agent as research_agent
from main_sandbox.main import coordinator as real_estate_agent

if __name__ == "__main__":
    # Create a Bureau to run all agents concurrently
    bureau = Bureau()

    # Add all agents to the bureau
    bureau.add(scoping_agent)
    bureau.add(community_analysis_agent)
    bureau.add(real_estate_intern)
    bureau.add(local_discovery_agent)
    bureau.add(mapbox_agent)
    bureau.add(research_agent)
    bureau.add(real_estate_agent)

    # Run all agents concurrently
    bureau.run()
