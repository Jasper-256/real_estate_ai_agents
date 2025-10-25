#!/usr/bin/env python3
"""
Example script to test the Sun Agent REST API
"""
import requests
import json

# Base URL for the agent
BASE_URL = "http://localhost:8001"

def test_status():
    """Test the GET /status endpoint"""
    print("Testing GET /status endpoint...")
    response = requests.get(f"{BASE_URL}/status")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_ask_question(question: str):
    """Test the POST /ask endpoint"""
    print(f"Testing POST /ask endpoint with question: '{question}'")

    payload = {
        "question": question
    }

    response = requests.post(
        f"{BASE_URL}/ask",
        json=payload,
        headers={"Content-Type": "application/json"}
    )

    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

if __name__ == "__main__":
    # Test status endpoint
    test_status()

    # Test asking about the sun
    test_ask_question("What is the temperature of the sun?")

    # Test asking about something else
    test_ask_question("What is the capital of France?")

    # Test another sun-related question
    test_ask_question("How old is the sun?")
