from vapi import Vapi
import os
from dotenv import load_dotenv
load_dotenv()

client = Vapi(token=os.getenv('VAPI_API_KEY'))

call = client.calls.create(
    assistant_id="6f723c39-5410-4b55-977f-ad80a1b947be",
    phone_number_id="f87d0e5f-73b5-4b44-bc98-23aa94b783f8",
    customer={"number": "+18589222159"},
)
print(call.id)
