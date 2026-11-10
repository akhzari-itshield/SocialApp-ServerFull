from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user
from ws_manager import manager
import models, schemas
from datetime import datetime

router = APIRouter(prefix="/messages", tags=["messages"])


def _check_permissions(user: models.User, message_type: str):
    if message_type in ("image", "file"):
        if user.permissions.get("send_file") is False:
            raise HTTPException(403, "ارسال فایل توسط مدیر غیرفعال شده")
    if message_type == "voice":
        if user.permissions.get("send_voice") is False:
            raise HTTPException(403, "ارسال پیام صوتی توسط مدیر غیرفعال شده")


@router.post("/", response_model=schemas.MessageOut)
async def send_message(data: schemas.MessageCreate, db: Session = Depends(get_db),
                       user=Depends(get_current_user)):
    chat = db.query(models.Chat).get(data.chat_id)
    if not chat or not chat.is_member(user.id):
        raise HTTPException(403, "Access denied")

    if chat.type == "channel":
        if chat.get_role(user.id) not in ("owner", "admin"):
            raise HTTPException(403, "فقط ادمین‌های کانال می‌توانند پیام بفرستند")

    _check_permissions(user, data.message_type)

    msg = models.Message(
        chat_id=data.chat_id, sender_id=user.id,
        content=data.content, message_type=data.message_type,
        file_url=data.file_url, reply_to_id=data.reply_to_id,
    )
    db.add(msg); db.commit(); db.refresh(msg)

    payload = {
        "event": "new_message",
        "data": {
            "id": msg.id, "chat_id": msg.chat_id, "sender_id": msg.sender_id,
            "content": msg.content, "message_type": msg.message_type,
            "file_url": msg.file_url, "reply_to_id": msg.reply_to_id,
            "created_at": msg.created_at.isoformat(),
        },
    }
    for m in chat.memberships:
        await manager.send_to_user(m.user_id, payload)
    return msg


@router.get("/{chat_id}", response_model=list[schemas.MessageOut])
def get_messages(
    chat_id: int,
    limit: int = 50,
    before_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    chat = db.query(models.Chat).get(chat_id)
    if not chat or not chat.is_member(user.id):
        raise HTTPException(403)


    deleted_for_me = db.query(models.MessageDeletion.message_id).filter(
        models.MessageDeletion.user_id == user.id
    ).subquery()

    q = db.query(models.Message).filter(
        models.Message.chat_id == chat_id,
        models.Message.is_deleted == False,
        ~models.Message.id.in_(deleted_for_me),
    )
    if before_id:
        q = q.filter(models.Message.id < before_id)
    return q.order_by(models.Message.id.desc()).limit(limit).all()[::-1]


@router.get("/{chat_id}/search")
def search_messages(chat_id: int, q: str = Query(...),
                    db: Session = Depends(get_db), user=Depends(get_current_user)):
    chat = db.query(models.Chat).get(chat_id)
    if not chat or not chat.is_member(user.id):
        raise HTTPException(403)

    deleted_for_me = db.query(models.MessageDeletion.message_id).filter(
        models.MessageDeletion.user_id == user.id
    ).subquery()

    return (
        db.query(models.Message)
        .filter(
            models.Message.chat_id == chat_id,
            models.Message.content.contains(q),
            models.Message.is_deleted == False,
            ~models.Message.id.in_(deleted_for_me),
        )
        .order_by(models.Message.id.desc())
        .limit(100)
        .all()
    )


@router.put("/{message_id}")
def edit_message(message_id: int, content: str, db: Session = Depends(get_db),
                 user=Depends(get_current_user)):
    msg = db.query(models.Message).get(message_id)
    if not msg or msg.sender_id != user.id:
        raise HTTPException(404)
    msg.content = content
    msg.is_edited = True
    msg.edited_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.delete("/{message_id}")
async def delete_message(message_id: int, for_everyone: bool = True,
                         db: Session = Depends(get_db), user=Depends(get_current_user)):
    msg = db.query(models.Message).get(message_id)
    if not msg:
        raise HTTPException(404)

    if for_everyone:

        if msg.sender_id != user.id:
            raise HTTPException(403, "Not your message")
        msg.is_deleted = True
        db.commit()

        chat = db.query(models.Chat).get(msg.chat_id)
        if chat:
            for m in chat.memberships:
                if m.user_id != user.id:
                    await manager.send_to_user(m.user_id, {
                        "event": "message_deleted",
                        "message_id": msg.id,
                        "chat_id": msg.chat_id,
                    })
    else:

        existing = db.query(models.MessageDeletion).filter(
            models.MessageDeletion.message_id == message_id,
            models.MessageDeletion.user_id == user.id,
        ).first()
        if not existing:
            db.add(models.MessageDeletion(
                message_id=message_id,
                user_id=user.id,
            ))
            db.commit()


    return {"ok": True}
