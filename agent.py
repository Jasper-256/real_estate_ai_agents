from datetime import datetime
from uuid import uuid4
import os
import time
from typing import Dict, Any

from openai import OpenAI
from uagents import Context, Protocol, Agent, Model
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)
from dotenv import load_dotenv
load_dotenv()
 
 
### Example Expert Assistant

## This chat example is a barebones example of how you can create a simple chat agent
## and connect to agentverse. In this example we will be prompting the ASI:One model to
## answer questions on a specific subject only. This acts as a simple placeholder for
## a more complete agentic system.
##

# REST API Models
class QuestionRequest(Model):
    question: str

class QuestionResponse(Model):
    timestamp: int
    answer: str
    agent_address: str
    subject: str

# the subject that this assistant is an expert in
subject_matter = "the sun"

# Model configuration
MODEL_NAME = "asi1-fast"

client = OpenAI(
    # By default, we are using the ASI:One LLM endpoint and model
    base_url='https://api.asi1.ai/v1',

    # You can get an ASI:One api key by creating an account at https://asi1.ai/dashboard/api-keys
    api_key=os.getenv('FETCH_AI_API_KEY'),
)

# Helper function to query the model
def query_model(question: str) -> str:
    """Query the ASI:One model with a question about the subject matter."""
    try:
        r = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": f"""
        You are a helpful assistant who only answers questions about {subject_matter}. If the user asks
        about any other topics, you should politely say that you do not know about them.
                """},
                {"role": "user", "content": question},
            ],
            max_tokens=2048,
        )
        return str(r.choices[0].message.content)
    except Exception as e:
        raise e

agent = Agent(
    name="ASI-agent",
    seed="657824399675823",
    port=8001,
    endpoint=["http://localhost:8001/submit"],
    mailbox=True,
    publish_agent_details=True,
)
 
# We create a new protocol which is compatible with the chat protocol spec. This ensures
# compatibility between agents
protocol = Protocol(spec=chat_protocol_spec)

# We define the handler for the chat messages that are sent to your agent
@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    # send the acknowledgement for receiving the message
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(), acknowledged_msg_id=msg.msg_id),
    )
 
    # collect up all the text chunks
    text = ''
    for item in msg.content:
        if isinstance(item, TextContent):
            text += item.text
 
    # query the model based on the user question
    response = 'I am afraid something went wrong and I am unable to answer your question at the moment'
    try:
        response = query_model(text)
    except:
        ctx.logger.exception('Error querying model')
 
    # send the response back to the user
    await ctx.send(sender, ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=[
            # we send the contents back in the chat message
            TextContent(type="text", text=response),
            # we also signal that the session is over, this also informs the user that we are not recording any of the
            # previous history of messages.
            EndSessionContent(type="end-session"),
        ]
    ))



@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    # we are not interested in the acknowledgements for this example, but they can be useful to
    # implement read receipts, for example.
    pass
 
 
# attach the protocol to the agent
agent.include(protocol, publish_manifest=True)


# REST API Endpoints

@agent.on_rest_get("/status", QuestionResponse)
async def handle_status(ctx: Context) -> Dict[str, Any]:
    """GET endpoint to check agent status"""
    return {
        "timestamp": int(time.time()),
        "answer": f"Sun agent is running and ready to answer questions about {subject_matter}",
        "agent_address": ctx.agent.address,
        "subject": subject_matter,
    }

@agent.on_rest_post("/ask", QuestionRequest, QuestionResponse)
async def handle_ask(ctx: Context, req: QuestionRequest) -> QuestionResponse:
    """POST endpoint to ask the sun agent questions"""
    ctx.logger.info(f"Received question via REST API: {req.question}")

    # Query the model with the user's question
    answer = 'I am afraid something went wrong and I am unable to answer your question at the moment'
    try:
        answer = query_model(req.question)
        ctx.logger.info(f"Generated answer: {answer}")
    except Exception as e:
        ctx.logger.exception(f'Error querying model: {e}')

    return QuestionResponse(
        timestamp=int(time.time()),
        answer=answer,
        agent_address=ctx.agent.address,
        subject=subject_matter,
    )


if __name__ == "__main__":
    agent.run()
