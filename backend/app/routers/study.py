from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
import httpx
from typing import Optional, Dict, Any
from app.core.security import bearer, get_current_user_id
from app.core.config import settings

router = APIRouter(prefix="/api/study", tags=["study"])

class StudyTaskRequest(BaseModel):
    task: str
    content: str
    options: Optional[Dict[str, Any]] = {}
    context: Optional[Dict[str, Any]] = {}

@router.post("/process")
async def process_task(data: StudyTaskRequest, credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    user_id = get_current_user_id(credentials)
    
    async with httpx.AsyncClient(timeout=90) as client:
        try:
            r = await client.post(
                f"{settings.study_agent_url}/process", 
                json=data.model_dump()
            )
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Study Agent communication failed: {exc}") from exc
