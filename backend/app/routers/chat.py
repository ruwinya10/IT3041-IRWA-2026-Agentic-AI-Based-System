from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
import httpx
from app.db.database import get_db
from app.db.models import Chat
from app.core.security import bearer, get_current_user_id
from app.core.config import settings

router = APIRouter(prefix="/api/chat", tags=["chat"])
class Ask(BaseModel):
    question: str

@router.post("/ask")
async def ask(data: Ask, credentials: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)):
    user_id = get_current_user_id(credentials)
    async with httpx.AsyncClient(timeout=100) as client:
        r = await client.post(f"{settings.coordinator_agent_url}/ask", json={"question": data.question, "user_id": user_id})
        r.raise_for_status()
        result = r.json()
    chat = Chat(user_id=user_id, question=data.question, answer=result["answer"])
    db.add(chat); db.commit()
    return result
