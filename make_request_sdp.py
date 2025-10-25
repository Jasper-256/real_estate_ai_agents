import requests
import json

url = "http://localhost:8002/process"

# Example document paths - update these with your actual document paths
payload = {
    "document_paths": [
        "home_inspection_docs/NaturalHazardDisclosureShort.pdf",
        # Add more document paths here as needed
        # "home_inspection_docs/inspection_report.pdf",
        # "home_inspection_docs/disclosure_form.pdf",
    ]
}

headers = {
    "Content-Type": "application/json"
}

print("Sending request to Seller Document Processor Agent...")
print(f"Processing {len(payload['document_paths'])} document(s)...\n")

# Make the POST request
try:
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    data = response.json()

    # Pretty print the structured response
    print("=" * 80)
    print("SELLER DOCUMENT PROCESSOR RESPONSE")
    print("=" * 80)

    print(f"\nDocuments Processed: {data['documents_processed']}")
    print(f"Agent Address: {data['agent_address']}")
    print(f"Timestamp: {data['timestamp']}")

    if data.get('call_id'):
        print(f"\n✓ VAPI Call Initiated Successfully!")
        print(f"   Call ID: {data['call_id']}")
    else:
        print(f"\n✗ VAPI call was not initiated")

    if data['processing_errors']:
        print(f"\n⚠️  Processing Errors ({len(data['processing_errors'])}):")
        for i, error in enumerate(data['processing_errors'], 1):
            print(f"   {i}. {error}")

    print("\n" + "=" * 80)
    print("GENERATED SYSTEM PROMPT FOR PHONE CALL AGENT")
    print("=" * 80)
    print(f"\n{data['system_prompt']}")
    print("\n" + "=" * 80)

except requests.exceptions.ConnectionError:
    print("❌ Error: Could not connect to the agent.")
    print("   Make sure the seller document processor agent is running on port 8002")
    print("   Run: python agents/seller_document_processor.py")
except requests.exceptions.HTTPError as e:
    print(f"❌ HTTP Error: {e}")
    print(f"   Response: {response.text}")
except Exception as e:
    print(f"❌ Error: {e}")
