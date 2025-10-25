import logging
import json

from fastapi import APIRouter, HTTPException, WebSocket, status
from fastapi.responses import JSONResponse
from app.core.config import settings
from pydantic import BaseModel

from teler.streams import StreamConnector, StreamType, StreamOp
from teler import AsyncClient

logger = logging.getLogger(__name__)
router = APIRouter()

class CallFlowRequest(BaseModel):
    call_id: str
    account_id: str
    from_number: str
    to_number: str

class CallRequest(BaseModel):
    from_number: str
    to_number: str
    
async def call_stream_handler(message: str):
    """
    Handle incoming websocket messages from Teler.
    """
    try:
        msg = json.loads(message)
        if msg["type"] == "audio":
            payload = json.dumps({"user_audio_chunk": msg["data"]["audio_b64"]})
            return (payload, StreamOp.RELAY)
        return ({}, StreamOp.PASS)
    except Exception as e:
        logger.error(f"Error in call stream handler: {e}")
        return ({}, StreamOp.PASS)
    


def remote_stream_handler():
    """
    Handle incoming websocket messages from Elevenlabs.
    """
    chunk_id = 1

    async def handler(message: str):
        try:
            nonlocal chunk_id
            msg = json.loads(message)
            if msg["type"] == "audio":
                payload = json.dumps(
                    {
                        "type": "audio",
                        "audio_b64": msg["audio_event"]["audio_base_64"],
                        "chunk_id": chunk_id,
                    }
                )
                chunk_id += 1
                return (payload, StreamOp.RELAY)
            elif msg["type"] == "interruption":
                payload = json.dumps({"type": "clear"})
                return (payload, StreamOp.RELAY)
            return ({}, StreamOp.PASS)
        except Exception as e:
            logger.error(f"Error in remote stream handler: {e}")
            return ({}, StreamOp.PASS)

    return handler

    
connector = StreamConnector(
    stream_type=StreamType.BIDIRECTIONAL,
    remote_url=settings.elevenlabs_websocket_url,
    call_stream_handler=call_stream_handler,
    remote_stream_handler=remote_stream_handler()
)

@router.post("/flow", status_code=status.HTTP_200_OK, include_in_schema=False)
async def stream_flow(payload: CallFlowRequest):
    """
    Build and return Stream flow.
    """
    logger.info("Call Flow")
    stream_flow = {
        "action": "stream",
        "ws_url": f"wss://{settings.server_domain}/api/v1/calls/media-stream",
        "chunk_size": 500,
        "sample_rate": settings.elevenlabs_sample_rate,
        "record": True
    }

    return JSONResponse(stream_flow)

@router.post("/initiate-call", status_code=status.HTTP_200_OK)
async def initiate_call(call_request: CallRequest):
    """
    Initiate a call using Teler SDK.
    """
    try:
        async with AsyncClient(api_key=settings.teler_api_key, timeout=10) as client:
            call = await client.calls.create(
                from_number=call_request.from_number,
                to_number=call_request.to_number,
                flow_url=f"https://{settings.server_domain}/api/v1/calls/flow",
                status_callback_url=f"https://{settings.server_domain}/api/v1/webhooks/receiver",
                record=True,
            )
            logger.info(f"Call created successfully: {call}")
            
        return JSONResponse(content={"success": True, "call_id": call.id})
    except Exception as e:
        logger.error(f"Failed to create call: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Failed to create call."
        )

@router.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connected.")
    await connector.bridge_stream(websocket)
