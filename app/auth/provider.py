from abc import ABC, abstractmethod
from pathlib import Path
from threading import Lock
from typing import Any, Optional

import firebase_admin
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth, credentials

from app.auth.models import AuthenticatedUser
from app.config import Settings, get_settings


class AuthProvider(ABC):
    @abstractmethod
    async def verify_token(self, token: str) -> AuthenticatedUser:
        """Verify a bearer token and return the normalized authenticated user."""


class FirebaseAuthProvider(AuthProvider):
    _init_lock = Lock()

    def __init__(self, settings: Settings):
        self.settings = settings
        self._ensure_initialized()

    def _ensure_initialized(self) -> None:
        if firebase_admin._apps:
            return

        with self._init_lock:
            if firebase_admin._apps:
                return

            options: dict[str, Any] = {}
            if self.settings.firebase_project_id:
                options["projectId"] = self.settings.firebase_project_id

            if self.settings.firebase_credentials_path:
                credential_path = Path(self.settings.firebase_credentials_path).expanduser()
                cred = credentials.Certificate(str(credential_path))
                firebase_admin.initialize_app(cred, options)
            else:
                firebase_admin.initialize_app(options=options or None)

    async def verify_token(self, token: str) -> AuthenticatedUser:
        try:
            decoded = auth.verify_id_token(
                token,
                check_revoked=True,
                app=firebase_admin.get_app(),
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired Firebase ID token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        return AuthenticatedUser(
            uid=decoded["uid"],
            email=decoded.get("email"),
            name=decoded.get("name"),
            claims=decoded,
        )


_bearer_scheme = HTTPBearer(auto_error=False)
_provider: Optional[AuthProvider] = None


def get_auth_provider(settings: Settings = Depends(get_settings)) -> AuthProvider:
    global _provider
    if _provider is None:
        _provider = FirebaseAuthProvider(settings)
    return _provider


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    provider: AuthProvider = Depends(get_auth_provider),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await provider.verify_token(credentials.credentials)
