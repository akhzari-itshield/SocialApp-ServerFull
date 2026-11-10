from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class PhoneRequest(BaseModel):
    phone_number: str

class OTPVerify(BaseModel):
    phone_number: str
    otp: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    display_name: Optional[str] = None

class UserOut(BaseModel):
    id: int
    phone_number: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool
    permissions: dict = Field(default_factory=dict)
    otp_code: Optional[str] = None
    otp_expires_at: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    created_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class UserPublic(BaseModel):
    id: int
    phone_number: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    last_seen: Optional[datetime] = None
    is_online: bool = False

class ProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None

class UserUpdate(BaseModel):
    is_active: Optional[bool] = None
    display_name: Optional[str] = None
    permissions: Optional[dict] = None

class MessageCreate(BaseModel):
    chat_id: int
    content: Optional[str] = None
    message_type: str = "text"
    file_url: Optional[str] = None
    reply_to_id: Optional[int] = None

class MessageOut(BaseModel):
    id: int
    chat_id: int
    sender_id: int
    content: Optional[str] = None
    message_type: str
    file_url: Optional[str] = None
    reply_to_id: Optional[int] = None
    is_deleted: bool
    is_edited: bool
    created_at: datetime
    class Config:
        from_attributes = True

class ChatCreate(BaseModel):
    type: str
    title: Optional[str] = None
    member_ids: List[int] = Field(default_factory=list)

class ChatOut(BaseModel):
    id: int
    type: str
    title: Optional[str] = None
    member_ids: List[int] = Field(default_factory=list)

class FolderCreate(BaseModel):
    name: str
    chat_ids: List[int] = Field(default_factory=list)

class AdminLogin(BaseModel):
    username: str
    password: str
class FolderCreate(BaseModel):
    name: str

class FolderUpdate(BaseModel):
    name: str
