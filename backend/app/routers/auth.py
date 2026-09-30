import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import User
from app.core.security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z .'-]{1,148}$")
PASSWORD_PATTERN = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,72}$"
)


class Register(BaseModel):
    email: EmailStr
    password: str
    full_name: str = ""


class Login(BaseModel):
    email: EmailStr
    password: str


@router.post("/register")
def register(data: Register, db: Session = Depends(get_db)):
    email = data.email.lower()
    full_name = data.full_name.strip()

    if not email.endswith("@gmail.com"):
        raise HTTPException(400, "Please use a valid Gmail address")
    if not NAME_PATTERN.fullmatch(full_name):
        raise HTTPException(400, "Enter a valid full name")
    if not PASSWORD_PATTERN.fullmatch(data.password):
        raise HTTPException(
            400,
            "Password must be 8-72 characters and include uppercase, lowercase, number, and special character"
        )
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "Email already registered")
    user = User(email=email, password_hash=hash_password(data.password), full_name=full_name)
    db.add(user); db.commit(); db.refresh(user)
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}


@router.post("/login")
def login(data: Login, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.lower()).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}
