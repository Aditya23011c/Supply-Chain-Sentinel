"""Auth routes + the require_user dependency that protects the API.
Set AUTH_DISABLED=1 to bypass auth (handy for quick dev / emergency demo)."""
import os
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from backend import security

router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)          # also gives /docs an "Authorize" button
AUTH_DISABLED = os.getenv("AUTH_DISABLED", "0") == "1"


class SignupBody(BaseModel):
    name: str = ""
    email: str
    password: str


class LoginBody(BaseModel):
    email: str
    password: str


def require_user(request: Request, creds: HTTPAuthorizationCredentials = Depends(bearer)):
    if AUTH_DISABLED:
        return {"name": "Dev", "email": "dev@local"}
    # EventSource (SSE) can't send headers, so the stream route also accepts ?token=
    token = creds.credentials if creds else request.query_params.get("token")
    user = security.get_user(security.verify_token(token)) if token else None
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


@router.post("/signup")
def signup(body: SignupBody):
    try:
        user = security.create_user(body.name, body.email, body.password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"token": security.make_token(user["email"]), "user": security.public(user)}


@router.post("/login")
def login(body: LoginBody):
    user = security.authenticate(body.email, body.password)
    if not user:
        raise HTTPException(401, "Incorrect email or password")
    return {"token": security.make_token(user["email"]), "user": security.public(user)}


@router.get("/me")
def me(user=Depends(require_user)):
    return security.public(user)
