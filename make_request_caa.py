import requests
import json

url = "http://localhost:8001/ask"

payload = {
    "location_name": "Daly City"
}

headers = {
    "Content-Type": "application/json"
}

# Make the POST request
response = requests.post(url, json=payload, headers=headers)
data = response.json()

# Pretty print the structured response
print(f"\n=== Community News Analysis for {data['location']} ===\n")

print("POSITIVE STORIES:")
for i, story in enumerate(data['positive_stories'], 1):
    print(f"{i}. {story['title']}")
    print(f"   {story['summary']}")
    print(f"   URL: {story.get('url', 'N/A')}\n")

print("\nNEGATIVE STORIES:")
for i, story in enumerate(data['negative_stories'], 1):
    print(f"{i}. {story['title']}")
    print(f"   {story['summary']}")
    print(f"   URL: {story.get('url', 'N/A')}\n")

print(f"\nCOMMUNITY SAFETY SCORE: {data['safety_score']}/10.0")
print(f"SCHOOL RATING: {data['school_rating']}/10.0")
print(f"OVERALL RATING: {data['overall_rating']}/10.0")
print(f"\nAgent Address: {data['agent_address']}")
print(f"Timestamp: {data['timestamp']}")
