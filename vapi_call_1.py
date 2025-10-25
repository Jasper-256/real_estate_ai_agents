from vapi import Vapi
import os
from dotenv import load_dotenv
load_dotenv()
from create_mock_data import build_system_prompt, select_mock_data

client = Vapi(token=os.getenv('VAPI_API_KEY'))

first_message = "Hello, this is a test call with an ai agent."
system_prompt = build_system_prompt(select_mock_data(1))
agent_id = "6f723c39-5410-4b55-977f-ad80a1b947be"

client.assistants.update(
    id=agent_id,
    first_message=first_message,
    model={
        "provider": "openai",
        "model": "gpt-4o",
        "messages": [{"role": "system", "content": system_prompt}],
    },
)

call = client.calls.create(
    assistant_id=agent_id,
    phone_number_id="1c14896d-6c86-4014-b9de-b5bc873c059b",
    customer={"number": "+18589222159"},
)
print(call.id)
