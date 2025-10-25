import requests
import json
from dotenv import load_dotenv
load_dotenv()
import os

headers = {
    'Authorization': f'Bearer {os.getenv('LANDING_AI_API_KEY')}'
}

url = 'https://api.va.landing.ai/v1/ade/parse'

# Set the model (optional)
data = {
    'model': 'dpt-2-latest'
}

# Upload a document 
document = open('document.pdf', 'rb')
files = {'document': document}

response = requests.post(url, files=files, data=data, headers=headers)
print(response.json())
