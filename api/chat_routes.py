import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai.chat_engine import AIChatEngine
from api.vital_routes import vitals_history, history_lock

logger = logging.getLogger(__name__)

router = APIRouter()

# Global Chat Engine singleton
chat_engine = AIChatEngine()

class MediaPayload(BaseModel):
    type: str # "image" or "video"
    base64: str
    mime_type: str

class ChatRequest(BaseModel):
    message: str
    session_id: str
    media: Optional[MediaPayload] = None
    search_enabled: Optional[bool] = False
    thinking_enabled: Optional[bool] = False

class ChatResponse(BaseModel):
    reply: str
    session_id: str
    vitals_context: Optional[Dict[str, Any]] = None

class ClearRequest(BaseModel):
    session_id: str

@router.get("/chat/sessions")
async def list_chat_sessions():
    """
    Returns list of all saved persistent chat sessions.
    """
    try:
        return chat_engine.list_sessions()
    except Exception as e:
        logger.error("Error listing chat sessions: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chat/session/{session_id}")
async def get_chat_session(session_id: str):
    """
    Retrieves the message history of a specific session.
    """
    try:
        messages = chat_engine.load_session(session_id)
        return {"session_id": session_id, "messages": messages}
    except Exception as e:
        logger.error("Error loading chat session: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/chat/session/{session_id}")
async def delete_chat_session(session_id: str):
    """
    Deletes a specific chat session file from memory and disk.
    """
    try:
        chat_engine.delete_session(session_id)
        return {"status": "deleted", "session_id": session_id}
    except Exception as e:
        logger.error("Error deleting chat session: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat/converse", response_model=ChatResponse)
async def converse(request: ChatRequest):
    """
    Exchanges messages with the clinical AI Assistant, injecting latest vitals.
    Supports media uploading, DuckDuckGo search, and thinking templates.
    """
    vitals_context = None
    
    # Retrieve the latest vital telemetry record from the broadcaster history (RAG)
    try:
        async with history_lock:
            if vitals_history:
                vitals_context = vitals_history[-1]
    except Exception as e:
        logger.error("Failed to fetch vital history for RAG context: %s", e)

    try:
        media_dict = request.media.dict() if request.media else None
        
        reply = await chat_engine.converse(
            session_id=request.session_id,
            user_message=request.message,
            vitals_context=vitals_context,
            media=media_dict,
            search_enabled=request.search_enabled,
            thinking_enabled=request.thinking_enabled
        )
        
        return ChatResponse(
            reply=reply,
            session_id=request.session_id,
            vitals_context=vitals_context
        )
    except Exception as e:
        logger.error("Error in chat conversation endpoint: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat/clear")
async def clear_chat_session(request: ClearRequest):
    """
    Clears the dialog history for the given session.
    """
    try:
        chat_engine.clear_session(request.session_id)
        return {"status": "cleared", "session_id": request.session_id}
    except Exception as e:
        logger.error("Error clearing chat session: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
