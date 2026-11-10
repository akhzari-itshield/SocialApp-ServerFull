from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from database import get_db
from config import settings
import models, schemas, auth

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/request-otp")
def request_otp(data: schemas.PhoneRequest, db: Session = Depends(get_db)):
    if data.phone_number.upper() == "SYSTEM":
    	raise HTTPException(400, "شماره نامعتبر است")
    user = db.query(models.User).filter(models.User.phone_number == data.phone_number).first()
    if not user:
        user = models.User(phone_number=data.phone_number,
                           display_name=data.phone_number[-4:])
        db.add(user)
        db.flush()
    if not user.is_active:
        raise HTTPException(403, "Account disabled by admin")
    otp = auth.generate_otp()
    user.otp_code = otp
    user.otp_expires_at = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
    db.commit()
    # In production: send SMS. For now print + show in admin panel
    print(f"[OTP] {data.phone_number} => {otp}")
    return {"message": "OTP generated. Contact admin to get the code."}

@router.post("/verify-otp", response_model=schemas.TokenResponse)
def verify_otp(data: schemas.OTPVerify, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.phone_number == data.phone_number).first()
    if not user or not user.otp_code or user.otp_code != data.otp:
        raise HTTPException(400, "Invalid OTP")
    if not user.otp_expires_at or user.otp_expires_at < datetime.utcnow():
        raise HTTPException(400, "OTP expired")
    if not user.is_active:
        raise HTTPException(403, "Account disabled")
    user.otp_code = None
    user.otp_expires_at = None
    db.commit()
    return {"access_token": auth.create_access_token(user.id),
            "user_id": user.id, "display_name": user.display_name}
