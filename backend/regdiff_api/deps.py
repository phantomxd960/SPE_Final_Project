"""FastAPI dependencies: database session and the authenticated user."""

from collections.abc import Iterator
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from regdiff_api.core.errors import ApiError
from regdiff_api.core.security import decode_token
from regdiff_common.db import get_sessionmaker
from regdiff_common.models import User

_bearer = HTTPBearer(auto_error=False)


def get_db() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


DbSession = Annotated[Session, Depends(get_db)]


def current_user(db: DbSession, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]) -> User:
    if credentials is None:
        raise ApiError(401, "Missing bearer token")
    try:
        user_id = int(decode_token(credentials.credentials)["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise ApiError(401, "Invalid or expired token") from exc
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(401, "User no longer exists")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
