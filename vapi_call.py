from vapi import Vapi
import os
from dotenv import load_dotenv
load_dotenv()

client = Vapi(token=os.getenv('VAPI_API_KEY'))

first_message = "Hello, this is a test call with an ai agent."
system_prompt = "Respond to the user's message with a friendly greeting and a brief introduction to the agent."
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
    phone_number_id="f87d0e5f-73b5-4b44-bc98-23aa94b783f8",
    customer={"number": "+18589222159"},
)
print(call.id)
