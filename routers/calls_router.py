from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user
import models

router = APIRouter(prefix="/calls", tags=["calls"])

@router.post("/initiate")
def initiate(callee_id: int, call_type: str = "voice",
             db: Session = Depends(get_db), user=Depends(get_current_user)):
    if call_type not in ("voice", "video"):
        raise HTTPException(400, "Invalid call type")
    callee = db.query(models.User).get(callee_id)
    if not callee or not callee.is_active:
        raise HTTPException(404, "Callee not found")
    call = models.CallSession(caller_id=user.id, callee_id=callee_id, call_type=call_type)
    db.add(call); db.commit(); db.refresh(call)
    return {"call_id": call.id, "status": call.status}

@router.post("/{call_id}/answer")
def answer(call_id: int, accept: bool, db: Session = Depends(get_db),
           user=Depends(get_current_user)):
    call = db.query(models.CallSession).get(call_id)
    if not call or call.callee_id != user.id:
        raise HTTPException(404)
    call.status = "active" if accept else "ended"
    db.commit()
    return {"ok": True}
