"""
Vapi Client - Low-level wrapper for Vapi REST API
==================================================

This is a reusable utility class for interacting with Vapi.
The vapi_agent.py uses this client to make actual phone calls.
"""

import requests
import os
from typing import Dict, Any, Optional


class VapiClient:
    """Client for interacting with Vapi REST API"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("VAPI_API_KEY")
        self.base_url = "https://api.vapi.ai"

        if not self.api_key:
            raise Exception("VAPI_API_KEY not found in environment variables")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Default IDs (can be overridden)
        self.assistant_id = os.getenv("VAPI_ASSISTANT_ID", "6f723c39-5410-4b55-977f-ad80a1b947be")
        self.phone_number_id = os.getenv("VAPI_PHONE_NUMBER_ID", "1c14896d-6c86-4014-b9de-b5bc873c059b")

    def update_assistant(
        self,
        system_prompt: str,
        first_message: str,
        assistant_id: Optional[str] = None
    ) -> bool:
        """
        Update the Vapi assistant with new system prompt and first message.

        Args:
            system_prompt: The system prompt for the assistant
            first_message: The opening message for the call
            assistant_id: Optional assistant ID (uses default if not provided)

        Returns:
            True if successful, False otherwise
        """
        aid = assistant_id or self.assistant_id
        url = f"{self.base_url}/assistant/{aid}"

        payload = {
            "firstMessage": first_message,
            "model": {
                "provider": "openai",
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    }
                ]
            }
        }

        try:
            response = requests.patch(url, headers=self.headers, json=payload)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Failed to update assistant: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return False

    def create_call(
        self,
        customer_phone: str,
        assistant_id: Optional[str] = None,
        phone_number_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Create a phone call via Vapi.

        Args:
            customer_phone: Phone number to call (e.g., "+18587331359")
            assistant_id: Optional assistant ID
            phone_number_id: Optional phone number ID

        Returns:
            Call ID if successful, None otherwise
        """
        aid = assistant_id or self.assistant_id
        pnid = phone_number_id or self.phone_number_id
        url = f"{self.base_url}/call/phone"

        payload = {
            "assistantId": aid,
            "phoneNumberId": pnid,
            "customer": {
                "number": customer_phone
            }
        }

        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("id")
        except requests.exceptions.RequestException as e:
            print(f"Failed to create call: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return None

    def get_call_status(self, call_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a call by ID"""
        url = f"{self.base_url}/call/{call_id}"

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Failed to get call status: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return None

    def wait_for_call_analysis(self, call_id: str, timeout_seconds: int = 120, poll_interval: float = 2.0) -> Optional[str]:
        """
        Wait for a call to complete and return its analysis summary.
        Vapi automatically generates analysis after call ends.

        Args:
            call_id: The ID of the call
            timeout_seconds: Maximum time to wait for analysis (default 120s)
            poll_interval: How often to poll for status (default 2s)

        Returns:
            The call summary from analysis, or None if timeout/error
        """
        import time

        start_time = time.time()

        print(f"Waiting for call {call_id} to complete and generate analysis...")

        while (time.time() - start_time) < timeout_seconds:
            call_data = self.get_call_status(call_id)

            if not call_data:
                print(f"Failed to get call status")
                time.sleep(poll_interval)
                continue

            status = call_data.get("status", "")
            print(f"Call status: {status}")

            # Check if call has ended
            if status == "ended":
                # Call has ended, check if analysis is available
                analysis = call_data.get("analysis", {})
                summary = analysis.get("summary", "")

                if summary:
                    print(f"✅ Analysis ready! Summary: {summary[:100]}...")
                    return summary
                else:
                    print("Call ended but analysis not yet ready, waiting...")
                    time.sleep(poll_interval)
                    continue

            # Call still in progress
            time.sleep(poll_interval)

        print(f"⏱️ Timeout waiting for call analysis after {timeout_seconds}s")
        return None
