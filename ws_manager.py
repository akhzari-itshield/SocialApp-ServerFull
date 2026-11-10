from fastapi import WebSocket
from typing import Dict, Set
from collections import defaultdict
from datetime import datetime


class ConnectionManager:
    def __init__(self):
        self.user_connections: Dict[int, Set[WebSocket]] = defaultdict(set)
        self.online_users: Dict[int, datetime] = {}

    async def connect(self, user_id: int, ws: WebSocket):
        await ws.accept()
        self.user_connections[user_id].add(ws)
        self.online_users[user_id] = datetime.utcnow()

    def disconnect(self, user_id: int, ws: WebSocket):
        self.user_connections[user_id].discard(ws)
        if not self.user_connections[user_id]:
            self.user_connections.pop(user_id, None)
            self.online_users.pop(user_id, None)

    async def send_to_user(self, user_id: int, message: dict):
        for ws in list(self.user_connections.get(user_id, [])):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(user_id, ws)

    def is_online(self, user_id: int) -> bool:
        return user_id in self.online_users

    def get_online_ids(self) -> list[int]:
        return list(self.online_users.keys())


manager = ConnectionManager()
