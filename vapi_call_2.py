from vapi import Vapi
import os
from dotenv import load_dotenv
load_dotenv()

def initiate_vapi_call(system_prompt: str, first_message: str = None) -> str:
    """
    Initiate a VAPI call with a custom system prompt.

    Args:
        system_prompt: The system prompt to use for the AI agent
        first_message: Optional first message. Defaults to a standard greeting.

    Returns:
        The call ID of the initiated call
    """
    client = Vapi(token=os.getenv('VAPI_API_KEY'))

    if first_message is None:
        first_message = "Hello, this is a call regarding the property we discussed. I'd like to talk about some details from the disclosure documents."

    agent_id = "5445e280-38b3-45c8-a3e8-4bb2a5a1b8b5"

    # Update the assistant with the new system prompt
    client.assistants.update(
        id=agent_id,
        first_message=first_message,
        model={
            "provider": "openai",
            "model": "gpt-4o",
            "messages": [{"role": "system", "content": system_prompt}],
        },
    )

    # Create the call
    call = client.calls.create(
        assistant_id=agent_id,
        phone_number_id="1c14896d-6c86-4014-b9de-b5bc873c059b",
        customer={"number": "+18589222159"},
    )

    return call.id


if __name__ == "__main__":
    # Test with a simple system prompt
    test_prompt = "You are a helpful real estate negotiator."
    call_id = initiate_vapi_call(test_prompt)
    print(f"Call initiated with ID: {call_id}")
