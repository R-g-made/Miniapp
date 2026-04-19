from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from jose import jwt, JWTError
from backend.core.config import settings
from backend.core.websocket_manager import manager
from backend.db.session import async_session_factory
from backend.crud.user import user_repository
from backend.schemas.websocket import WSEventMessage, WSMessageType
from loguru import logger

router = APIRouter()

async def get_token_user_id(token: str) -> str:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id = payload.get("sub")
        if user_id is None:
            return None
        return str(user_id)
    except JWTError as e:
        logger.warning(f"WebSocket: JWT Decode Error: {e}")
        return None

@router.websocket("/events")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...)
):
    user_id = await get_token_user_id(token)
    if not user_id:
        logger.warning(f"WebSocket: Connection rejected for token: {token[:10]}...")
        await websocket.accept()
        error_msg = WSEventMessage(
            type=WSMessageType.ERROR,
            data={"message": "Unauthorized"}
        )
        await websocket.send_text(error_msg.model_dump_json())
        await websocket.close(code=1008)
        return

    await manager.connect(websocket, user_id)
    logger.info(f"WebSocket: User {user_id} connected successfully")
    
    try:
        auth_msg = WSEventMessage(
            type=WSMessageType.AUTH_SUCCESS,
            data={"user_id": user_id}
        )
        await websocket.send_text(auth_msg.model_dump_json())
        
        await manager.listen_and_deliver(websocket, user_id)
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
        logger.info(f"WebSocket: User {user_id} disconnected")
    except Exception as e:
        manager.disconnect(websocket, user_id)
        logger.error(f"WebSocket: Critical error for user {user_id}: {e}")