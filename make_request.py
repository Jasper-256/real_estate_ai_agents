import requests
import json

url = "http://localhost:8001/ask"

payload = {
    "city_name": "San Francisco"
}

headers = {
    "Content-Type": "application/json"
}

# Make the POST request
response = requests.post(url, json=payload, headers=headers)
data = response.json()

# Pretty print the structured response
print(f"\n=== Community News Analysis for {data['city']} ===\n")

print("POSITIVE STORIES:")
for i, story in enumerate(data['positive_stories'], 1):
    print(f"{i}. {story['title']}")
    print(f"   {story['summary']}\n")

print("\nNEGATIVE STORIES:")
for i, story in enumerate(data['negative_stories'], 1):
    print(f"{i}. {story['title']}")
    print(f"   {story['summary']}\n")

print(f"\nCOMMUNITY SAFETY SCORE: {data['safety_score']}/10.0")
print(f"Agent Address: {data['agent_address']}")
print(f"Timestamp: {data['timestamp']}")
