from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class AuthenticatedUser:
    uid: str
    email: Optional[str] = None
    name: Optional[str] = None
    claims: dict[str, Any] = field(default_factory=dict)
