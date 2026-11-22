"""Login with email and password; returns a JWT (SEC-1)."""

from fastapi import APIRouter
from sqlalchemy import select

from regdiff_api.core.errors import ApiError
from regdiff_api.core.security import create_token, verify_password
from regdiff_api.deps import CurrentUser, DbSession
from regdiff_api.schemas import LoginRequest, TokenResponse, UserOut
from regdiff_common.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: DbSession) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise ApiError(401, "Wrong email or password")
    token, expires_in = create_token(user.id, user.role)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user
