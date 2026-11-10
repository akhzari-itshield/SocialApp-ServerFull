from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError, jwt
from datetime import datetime
from config import settings
from ws_manager import manager
from database import SessionLocal
import models, json

router = APIRouter()


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket, token: str = Query(...)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        await websocket.close(code=4001)
        return

    db = SessionLocal()
    user = db.query(models.User).get(user_id)
    if not user or not user.is_active:
        await websocket.close(code=4003)
        db.close()
        return

    was_online = manager.is_online(user_id)
    await manager.connect(user_id, websocket)


    if not was_online:
        for other_id in manager.get_online_ids():
            if other_id != user_id:
                await manager.send_to_user(other_id, {
                    "event": "user_online",
                    "user_id": user_id,
                })

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            event = data.get("event")

            if event == "typing":
                chat = db.query(models.Chat).get(data.get("chat_id"))
                if chat and chat.is_member(user_id):
                    for m in chat.memberships:
                        if m.user_id != user_id:
                            await manager.send_to_user(m.user_id, {
                                "event": "typing",
                                "chat_id": chat.id,
                                "user_id": user_id,
                            })

            elif event == "webrtc_signal":
                target_id = data.get("target_id")
                if target_id:
                    await manager.send_to_user(target_id, {
                        "event": "webrtc_signal",
                        "from_id": user_id,
                        "signal": data.get("signal"),
                    })

            elif event in ("call_request", "call_accept", "call_reject", "call_end"):
                target_id = data.get("target_id")
                if target_id:
                    await manager.send_to_user(target_id, {
                        "event": event,
                        "from_id": user_id,
                        "call_type": data.get("call_type", "video"),
                    })

            # ⭐ Read receipt: کاربر پیام را خواند
            elif event == "read_receipt":
                chat_id = data.get("chat_id")
                message_id = data.get("message_id")
                if chat_id and message_id:
                    chat = db.query(models.Chat).get(chat_id)
                    if chat and chat.is_member(user_id):
                        for m in chat.memberships:
                            if m.user_id == user_id:
                                if m.last_read_message_id is None or message_id > m.last_read_message_id:
                                    m.last_read_message_id = message_id
                                    db.commit()
                                break

                        for m in chat.memberships:
                            if m.user_id != user_id:
                                await manager.send_to_user(m.user_id, {
                                    "event": "read_receipt",
                                    "chat_id": chat_id,
                                    "user_id": user_id,
                                    "last_read_message_id": message_id,
                                })

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(user_id, websocket)
        db.close()


        if not manager.is_online(user_id):
            now = datetime.utcnow()
            db2 = SessionLocal()
            try:
                u = db2.query(models.User).get(user_id)
                if u:
                    u.last_seen = now
                    db2.commit()
            finally:
                db2.close()

            for other_id in manager.get_online_ids():
                if other_id != user_id:
                    await manager.send_to_user(other_id, {
                        "event": "user_offline",
                        "user_id": user_id,
                        "last_seen": now.isoformat(),
                    })
