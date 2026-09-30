from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.database import Base, engine
from app.routers.auth import router as auth_router
from app.routers.documents import router as documents_router
from app.routers.chat import router as chat_router
from app.routers.study import router as study_router

Base.metadata.create_all(bind=engine)
app = FastAPI(title=settings.app_name)
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_url], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(study_router)
@app.get("/health")
def health(): return {"status": "ok"}
