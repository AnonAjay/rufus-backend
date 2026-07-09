from app.auth.models import AuthenticatedUser
from app.auth.provider import get_current_user


# TODO(auth-jwt-interface): Keep route dependencies importing this module so the
# Firebase provider can be swapped for a future ecosystem auth provider without
# changing business logic.
CurrentUser = AuthenticatedUser
