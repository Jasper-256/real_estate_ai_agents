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

def parse_pdf(pdf_path):
    # Upload a document 
    document = open(pdf_path, 'rb')
    files = {'document': document}

    response = requests.post(url, files=files, data=data, headers=headers)
    return response.json()['markdown']

if __name__ == '__main__':
    print(parse_pdf('home_inspection_docs/NaturalHazardDisclosureShort.pdf'))
