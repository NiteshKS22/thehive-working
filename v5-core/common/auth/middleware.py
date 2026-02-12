import os
import jwt
import logging
from fastapi import Request, HTTPException, status, Depends
from typing import Optional, List, Union
from pydantic import BaseModel

logger = logging.getLogger("auth-middleware")

# Configuration (Dynamic fetch preferred for tests, but keeping globals for perf)
def get_config():
    return {
        "DEV_MODE": os.getenv("DEV_MODE", "false").lower() == "true",
        "JWT_SECRET": os.getenv("JWT_SECRET", "dev-secret-do-not-use-in-prod"),
        "JWT_ALGORITHM": os.getenv("JWT_ALGORITHM", "HS256"),
        "OIDC_ISSUER": os.getenv("OIDC_ISSUER", "https://auth.example.com"),
        "JWKS_URL": os.getenv("JWKS_URL", "")
    }

def validate_auth_config():
    """
    Validates authentication configuration at startup.
    Raises RuntimeError if insecure configuration is detected.
    """
    config = get_config()
    algo = config["JWT_ALGORITHM"]

    if algo != "HS256" and not config["JWKS_URL"] and not config["JWT_SECRET"]:
        msg = f"CRITICAL: {algo} requires JWKS/PublicKey (JWKS_URL or JWT_SECRET PEM). Service startup aborted."
        logger.critical(msg)
        raise RuntimeError(msg)

    logger.info(f"Auth Config Validated: Algorithm={algo}, DevMode={config['DEV_MODE']}")

class AuthContext(BaseModel):
    user_id: str
    tenant_id: str
    roles: List[str] = []

async def get_auth_context(request: Request) -> AuthContext:
    config = get_config()

    if config["DEV_MODE"]:
        dev_tenant = request.headers.get("X-Dev-Tenant", "dev-tenant")
        dev_user = request.headers.get("X-Dev-User", "dev-user")
        dev_roles_str = request.headers.get("X-Dev-Roles", "SYSTEM_ADMIN")
        dev_roles = dev_roles_str.split(",") if "," in dev_roles_str else [dev_roles_str]

        logger.warning(f"DEV_MODE: Bypass Auth for user={dev_user} tenant={dev_tenant}")
        return AuthContext(user_id=dev_user, tenant_id=dev_tenant, roles=dev_roles)

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid Authorization header")

    token = auth_header.split(" ")[1]

    try:
        # Configuration validated at startup, safe to use here

        payload = jwt.decode(
            token,
            config["JWT_SECRET"], # Or public key
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
