import os
import jwt
import logging
import sys
from fastapi import Request, HTTPException, status, Depends
from typing import Optional, List, Union
from pydantic import BaseModel

logger = logging.getLogger("auth-middleware")

# Configuration (Dynamic fetch preferred for tests, but keeping globals for perf)
def get_config():
    return {
        "DEV_MODE": os.getenv("DEV_MODE", "false").lower() == "true",
        "ALLOW_DEV_OVERRIDES": os.getenv("ALLOW_DEV_OVERRIDES", "false").lower() == "true",
        "JWT_SECRET": os.getenv("JWT_SECRET", "dev-secret-do-not-use-in-prod"),
        "JWT_ALGORITHM": os.getenv("JWT_ALGORITHM", "HS256"),
        "OIDC_ISSUER": os.getenv("OIDC_ISSUER", "https://auth.example.com"),
        "JWKS_URL": os.getenv("JWKS_URL", "")
    }

# CHECK 3: RS256 Guardrail (Startup Check)
_config = get_config()
if _config["JWT_ALGORITHM"] != "HS256" and not _config["JWKS_URL"] and not _config["JWT_SECRET"]:
    msg = "CRITICAL: RS256 requires JWKS/PublicKey (JWKS_URL or JWT_SECRET PEM)"
    logger.critical(msg)
    sys.exit(msg)

class AuthContext(BaseModel):
    user_id: str
    tenant_id: str
    roles: List[str] = []

async def get_auth_context(request: Request) -> AuthContext:
    config = get_config()

    if config["DEV_MODE"]:
        # Safe Defaults
        user_id = "dev-user"
        tenant_id = "dev-tenant"
        roles = ["SYSTEM_ADMIN"]

        # Check overrides if allowed
        if config["ALLOW_DEV_OVERRIDES"]:
            if "X-Dev-Tenant" in request.headers:
                tenant_id = request.headers["X-Dev-Tenant"]
                logger.info(f"DEV_MODE: Tenant override -> {tenant_id}")
            if "X-Dev-User" in request.headers:
                user_id = request.headers["X-Dev-User"]
            if "X-Dev-Roles" in request.headers:
                roles_str = request.headers["X-Dev-Roles"]
                roles = roles_str.split(",") if "," in roles_str else [roles_str]
        elif "X-Dev-Tenant" in request.headers:
            logger.warning("DEV_MODE: Header overrides present but ALLOW_DEV_OVERRIDES=False. Ignoring.")

        return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=roles)

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid Authorization header")

    token = auth_header.split(" ")[1]

    try:
        payload = jwt.decode(
            token,
            config["JWT_SECRET"],
            algorithms=[config["JWT_ALGORITHM"]],
            audience="v5-core",
            issuer=config["OIDC_ISSUER"]
        )

        tenant_id = payload.get("tenant_id")
        user_id = payload.get("sub")
        roles_raw = payload.get("roles", [])

        if not tenant_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token missing tenant_id")
        if not user_id:
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token missing sub (user_id)")

        if isinstance(roles_raw, str):
            roles = [roles_raw]
        elif isinstance(roles_raw, list):
            roles = roles_raw
        else:
            roles = []

        return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=roles)

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

def require_role(required_roles: List[str]):
    def dependency(ctx: AuthContext = Depends(get_auth_context)):
        if not any(role in ctx.roles for role in required_roles):
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Insufficient role. Required: {required_roles}")
        return ctx
    return dependency
