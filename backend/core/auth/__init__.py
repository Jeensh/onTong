"""Authentication abstraction layer.

Swap providers by changing AUTH_PROVIDER in .env:
  - "noop"   : No auth, always returns dev user (default)
  - "custom" : Implement your own AuthProvider subclass

Example for adding SSO/LDAP/OIDC:
  1. Create a new file (e.g., sso_provider.py) implementing AuthProvider
  2. Register it in _PROVIDERS below
  3. Set AUTH_PROVIDER=sso in .env
"""

from backend.core.auth.models import User
from backend.core.auth.base import AuthProvider
from backend.core.auth.deps import get_current_user

__all__ = ["User", "AuthProvider", "get_current_user"]
