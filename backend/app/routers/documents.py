import os
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pypdf import PdfReader
from app.db.database import get_db
from app.db.models import Document
from app.core.config import settings
from app.core.security import bearer, get_current_user_id
from app.rag.vector_store import add_document

router = APIRouter(prefix="/api/documents", tags=["documents"])
os.makedirs(settings.upload_dir, exist_ok=True)

@router.post("/upload")
async def upload(file: UploadFile = File(...), credentials: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)):
    user_id = get_current_user_id(credentials)
    is_pdf = (file.filename and file.filename.lower().endswith(".pdf")) or (
        file.content_type in ["application/pdf", "application/x-pdf", "application/octet-stream"]
    )
    if not is_pdf:
        raise HTTPException(400, "Only PDF files (.pdf) are supported.")

    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "File is too large")

    safe_name = os.path.basename(file.filename or "document.pdf").replace(" ", "_")
    path = os.path.join(settings.upload_dir, f"{user_id}_{safe_name}")
    with open(path, "wb") as f:
        f.write(data)

    text = ""
    try:
        reader = PdfReader(path)
        extracted = []
        for page in reader.pages:
            try:
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    extracted.append(page_text.strip())
            except Exception:
                continue
        text = "\n\n".join(extracted)
    except Exception as e:
        raise HTTPException(400, f"Could not read PDF: {str(e)}")

    if not text.strip():
        raise HTTPException(400, "This PDF contains no extractable text. It may be a scanned image. Please upload a PDF with selectable text.")

    doc = Document(user_id=user_id, filename=safe_name, stored_path=path)
    db.add(doc)
    db.commit()
    db.refresh(doc)

    chunks = add_document(doc.id, user_id, text, safe_name)
    return {"document_id": doc.id, "filename": safe_name, "chunks_indexed": chunks}
