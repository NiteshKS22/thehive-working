import os
import jwt
import logging
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict
from pydantic import BaseModel

logger = logging.getLogger("auth-middleware")

# Configuration
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-do-not-use-in-prod") # For HS256 (Dev) or RS256 (Prod/OIDC)
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
OIDC_ISSUER = os.getenv("OIDC_ISSUER", "https://auth.example.com")

class AuthContext(BaseModel):
    user_id: str
    tenant_id: str
    roles: List[str] = []
    permissions: List[str] = [] # Could be fetched from DB or embedded in token

async def get_auth_context(request: Request) -> AuthContext:
    if DEV_MODE:
        # Bypass validation for local dev/test
        # Allow header override for testing isolation
        dev_tenant = request.headers.get("X-Dev-Tenant", "dev-tenant")
        dev_user = request.headers.get("X-Dev-User", "dev-user")
        dev_roles = request.headers.get("X-Dev-Roles", "SYSTEM_ADMIN").split(",")
        return AuthContext(user_id=dev_user, tenant_id=dev_tenant, roles=dev_roles)

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid Authorization header")

    token = auth_header.split(" ")[1]

    try:
        # In production, we'd fetch JWKS. Here assuming shared secret or simple key for Phase E1 start.
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], audience="v5-core", issuer=OIDC_ISSUER)

        tenant_id = payload.get("tenant_id")
        user_id = payload.get("sub")
        roles = payload.get("roles", [])

        if not tenant_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token missing tenant_id")

        return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=roles)

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

def require_role(required_roles: List[str]):
    def dependency(ctx: AuthContext):
        if not any(role in ctx.roles for role in required_roles):
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return ctx
    return dependency
