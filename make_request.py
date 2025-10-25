import requests
import json

url = "http://localhost:8001/ask"

payload = {
    "question": "What is the temperature of the sun?"
}

headers = {
    "Content-Type": "application/json"
}

# Make the POST request
response = requests.post(url, json=payload, headers=headers)
data = response.json()
print(data["answer"])
