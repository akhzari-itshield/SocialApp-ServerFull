from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, BigInteger
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    phone_number = Column(String, unique=True, index=True, nullable=False)
    display_name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    otp_code = Column(String, nullable=True)
    otp_expires_at = Column(DateTime, nullable=True)
    permissions = Column(JSON, default=dict)
    last_seen = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    messages = relationship("Message", back_populates="sender", cascade="all, delete-orphan")
    memberships = relationship("ChatMember", back_populates="user", cascade="all, delete-orphan")
    folders = relationship("ChatFolder", back_populates="user", cascade="all, delete-orphan")
    files = relationship("FileRecord", back_populates="uploader", cascade="all, delete-orphan")
    deletions = relationship("MessageDeletion", cascade="all, delete-orphan")

    @property
    def chats(self):
        return [m.chat for m in self.memberships]


class AdminUser(Base):
    __tablename__ = "admin_users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_super = Column(Boolean, default=False)


class Chat(Base):
    __tablename__ = "chats"
    id = Column(Integer, primary_key=True)
    type = Column(String, nullable=False)
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    memberships = relationship("ChatMember", back_populates="chat", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")
    files = relationship("FileRecord", back_populates="chat")

    @property
    def members(self):
        return [m.user for m in self.memberships]

    def is_member(self, user_id: int) -> bool:
        return any(m.user_id == user_id for m in self.memberships)

    def get_role(self, user_id: int):
        for m in self.memberships:
            if m.user_id == user_id:
                return m.role
        return None


class ChatMember(Base):
    __tablename__ = "chat_members"
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role = Column(String, default="member")
    last_read_message_id = Column(Integer, nullable=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    chat = relationship("Chat", back_populates="memberships")
    user = relationship("User", back_populates="memberships")


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=True)
    message_type = Column(String, default="text")
    file_url = Column(String, nullable=True)
    reply_to_id = Column(Integer, ForeignKey("messages.id"), nullable=True)
    is_deleted = Column(Boolean, default=False)
    is_edited = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    edited_at = Column(DateTime, nullable=True)

    sender = relationship("User", back_populates="messages")
    chat = relationship("Chat", back_populates="messages")


class MessageDeletion(Base):

    __tablename__ = "message_deletions"
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    deleted_at = Column(DateTime(timezone=True), server_default=func.now())


class ChatFolder(Base):
    __tablename__ = "chat_folders"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, nullable=False)
    chat_ids = Column(JSON, default=list)
    user = relationship("User", back_populates="folders")


class CallSession(Base):
    __tablename__ = "call_sessions"
    id = Column(Integer, primary_key=True)
    caller_id = Column(Integer, ForeignKey("users.id"))
    callee_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    chat_id = Column(Integer, nullable=True)
    call_type = Column(String)
    status = Column(String, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FileRecord(Base):
    __tablename__ = "files"
    id = Column(Integer, primary_key=True)
    uploader_id = Column(Integer, ForeignKey("users.id"))
    stored_name = Column(String, nullable=False)
    original_name = Column(String, nullable=True)
    mime_type = Column(String, nullable=True)
    size_bytes = Column(BigInteger, default=0)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    uploader = relationship("User", back_populates="files")
    chat = relationship("Chat", back_populates="files")
