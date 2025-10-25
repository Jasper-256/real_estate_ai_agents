from datetime import datetime, timezone
from uuid import uuid4
import os
import sys
import time
from typing import Dict, Any, List

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

# Import the parse_pdf function
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from parse_pdf import parse_pdf

### Seller Document Processor Agent
## This agent processes seller documents (inspection reports, disclosure forms, etc.)
## and generates a system prompt for a phone call agent to negotiate house prices

# REST API Models
class DocumentProcessRequest(Model):
    document_paths: List[str]

class SystemPromptResponse(Model):
    timestamp: int
    system_prompt: str
    agent_address: str
    documents_processed: int
    processing_errors: List[str]

# Model configuration
MODEL_NAME = "asi1-fast"

client = OpenAI(
    base_url='https://api.asi1.ai/v1',
    api_key=os.getenv('FETCH_AI_API_KEY'),
)

def process_documents(document_paths: List[str]) -> tuple[List[Dict[str, str]], List[str]]:
    """
    Process a list of documents and extract markdown content.
    Returns a tuple of (successful_documents, errors)
    """
    processed_docs = []
    errors = []

    for doc_path in document_paths:
        try:
            # Check if file exists
            if not os.path.exists(doc_path):
                errors.append(f"File not found: {doc_path}")
                continue

            # Extract markdown from document
            markdown_content = parse_pdf(doc_path)

            processed_docs.append({
                "filename": os.path.basename(doc_path),
                "content": markdown_content,
                "path": doc_path
            })
        except Exception as e:
            errors.append(f"Error processing {doc_path}: {str(e)}")

    return processed_docs, errors

def generate_phone_agent_prompt(documents: List[Dict[str, str]]) -> str:
    """
    Generate a system prompt for the phone call agent based on processed documents.
    """
    # Combine all document contents
    all_content = "\n\n".join([
        f"=== Document: {doc['filename']} ===\n{doc['content']}"
        for doc in documents
    ])

    # Use ASI:One to analyze documents and extract key issues
    try:
        analysis_response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": """You are an expert real estate analyst.
                Analyze the provided seller disclosure documents and identify all issues,
                defects, damages, repairs needed, and concerns with the property.
                Organize them by severity and estimated repair costs.
                Do not focus on document completeness, only issues with the property.
                Your response should always be below 500 words."""},
                {"role": "user", "content": f"Analyze these seller documents:\n\n{all_content}"},
            ],
            max_tokens=2000,
        )
        analysis = str(analysis_response.choices[0].message.content)
        print(analysis)
    except Exception:
        analysis = "Unable to perform detailed analysis."

    # Create the system prompt template
    system_prompt = f"""You are a skilled real estate negotiator making a phone call to discuss a property purchase.
Your goal is to negotiate a lower price based on issues disclosed in the seller's documents.

DOCUMENT ANALYSIS:
<analysis>
{analysis}
</analysis>

YOUR ROLE:
- You are calling to discuss concerns about the property based on the disclosure documents
- Be professional, polite, and respectful throughout the conversation
- Reference specific issues from the documents above
- Ask clarifying questions about repairs, timelines, and costs
- Negotiate for either: (1) a price reduction, (2) seller-paid repairs, or (3) credits at closing
- Use market data and repair cost estimates to justify your requests

NEGOTIATION STRATEGY:
1. Start by acknowledging interest in the property
2. Bring up specific concerns from the documents (be specific with details)
3. Ask about the history and current status of each issue
4. Present repair cost estimates or inspection findings
5. Propose fair price adjustments based on the issues
6. Be prepared to compromise but maintain a firm position on major issues
7. Keep the conversation collaborative - you want a win-win outcome

CONVERSATION GUIDELINES:
- Listen actively and take notes on seller responses
- Be empathetic to the seller's situation while advocating for your interests
- Use phrases like "I noticed in the disclosure that..." or "The inspection report shows..."
- Avoid being confrontational; frame issues as mutual problem-solving opportunities
- If the seller is defensive, acknowledge their perspective before presenting your concerns
- Document any agreements or commitments made during the call

Remember: Your goal is to secure the best possible deal while maintaining a positive relationship with the seller."""

    return system_prompt

agent = Agent(
    name="Seller Document Processor",
    seed="seller_doc_proc_123",
    port=8002,
    endpoint=["http://localhost:8002/submit"],
    mailbox=True,
    publish_agent_details=True,
)

protocol = Protocol(spec=chat_protocol_spec)

@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    # Send acknowledgement
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(), acknowledged_msg_id=msg.msg_id),
    )

    # Collect text content (expecting file paths)
    text = ''
    for item in msg.content:
        if isinstance(item, TextContent):
            text += item.text

    # Parse document paths (expecting comma-separated or newline-separated paths)
    document_paths = [path.strip() for path in text.replace('\n', ',').split(',') if path.strip()]

    if not document_paths:
        response = "Please provide document paths to process (comma or newline separated)."
    else:
        # Process documents
        try:
            processed_docs, errors = process_documents(document_paths)

            if not processed_docs:
                response = f"Failed to process any documents. Errors:\n" + "\n".join(errors)
            else:
                # Generate system prompt
                system_prompt = generate_phone_agent_prompt(processed_docs)

                response = f"""Successfully processed {len(processed_docs)} document(s).

GENERATED SYSTEM PROMPT FOR PHONE AGENT:
{'='*60}
{system_prompt}
{'='*60}

Processed documents: {', '.join([doc['filename'] for doc in processed_docs])}
"""
                if errors:
                    response += f"\n\nWarnings/Errors:\n" + "\n".join(errors)
        except Exception as e:
            ctx.logger.exception('Error processing documents')
            response = f"Error processing documents: {str(e)}"

    # Send response
    await ctx.send(sender, ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[
            TextContent(type="text", text=response),
            EndSessionContent(type="end-session"),
        ]
    ))

@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass

agent.include(protocol, publish_manifest=True)

# REST API Endpoints

@agent.on_rest_get("/status", SystemPromptResponse)
async def handle_status(ctx: Context) -> Dict[str, Any]:
    """GET endpoint to check agent status"""
    return {
        "timestamp": int(time.time()),
        "system_prompt": "Seller Document Processor is running and ready to process documents",
        "agent_address": ctx.agent.address,
        "documents_processed": 0,
        "processing_errors": [],
    }

@agent.on_rest_post("/process", DocumentProcessRequest, SystemPromptResponse)
async def handle_process(ctx: Context, req: DocumentProcessRequest) -> SystemPromptResponse:
    """POST endpoint to process seller documents and generate phone agent system prompt"""
    ctx.logger.info(f"Received document processing request with {len(req.document_paths)} documents")

    try:
        # Process documents
        processed_docs, errors = process_documents(req.document_paths)

        if not processed_docs:
            return SystemPromptResponse(
                timestamp=int(time.time()),
                system_prompt="Failed to process any documents",
                agent_address=ctx.agent.address,
                documents_processed=0,
                processing_errors=errors,
            )

        # Generate system prompt
        system_prompt = generate_phone_agent_prompt(processed_docs)
        ctx.logger.info(f"Successfully generated system prompt from {len(processed_docs)} documents")

        return SystemPromptResponse(
            timestamp=int(time.time()),
            system_prompt=system_prompt,
            agent_address=ctx.agent.address,
            documents_processed=len(processed_docs),
            processing_errors=errors,
        )
    except Exception as e:
        ctx.logger.exception(f'Error in document processing: {e}')
        return SystemPromptResponse(
            timestamp=int(time.time()),
            system_prompt=f"Error: {str(e)}",
            agent_address=ctx.agent.address,
            documents_processed=0,
            processing_errors=[str(e)],
        )


if __name__ == "__main__":
    agent.run()
