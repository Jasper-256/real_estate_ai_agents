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

print(f"OVERALL RATING: {data['overall_score']}/10.0")
print(f"Explanation: {data['overall_explanation']}\n")

print("=" * 60)
print("\nSAFETY ANALYSIS:")
print(f"Safety Score: {data['safety_score']}/10.0\n")

print("POSITIVE STORIES:")
for i, story in enumerate(data['positive_stories'], 1):
    print(f"{i}. {story['title']}")
    print(f"   {story['summary']}")
    print(f"   URL: {story.get('url', 'N/A')}\n")

print("NEGATIVE STORIES:")
for i, story in enumerate(data['negative_stories'], 1):
    print(f"{i}. {story['title']}")
    print(f"   {story['summary']}")
    print(f"   URL: {story.get('url', 'N/A')}\n")

print("=" * 60)
print("\nSCHOOLS ANALYSIS:")
print(f"School Rating: {data['school_rating']}/10.0")
print(f"Explanation: {data['school_explanation']}\n")

print("=" * 60)
print("\nHOUSING MARKET DATA:")
print(f"Average Price per Square Foot: ${data['housing_price_per_square_foot']}")
print(f"Average House Size: {data['average_house_size_square_foot']} sq ft")
if data['housing_price_per_square_foot'] > 0 and data['average_house_size_square_foot'] > 0:
    avg_price = data['housing_price_per_square_foot'] * data['average_house_size_square_foot']
    print(f"Estimated Average Home Price: ${avg_price:,.0f}")

print("\n" + "=" * 60)
print(f"\nAgent Address: {data['agent_address']}")
print(f"Timestamp: {data['timestamp']}")
