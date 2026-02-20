import unittest
from unittest.mock import MagicMock, patch
import os
import sys
import jwt
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient

# Add common to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from common.auth import middleware
from common.auth.middleware import get_auth_context, require_role, require_permission, AuthContext
from common.auth.rbac import ROLE_ADMIN, ROLE_ANALYST, PERM_ALERT_READ, PERM_ALERT_INGEST

app = FastAPI()

@app.get("/protected")
def protected_endpoint(auth: AuthContext = Depends(get_auth_context)):
    return {"user": auth.user_id, "tenant": auth.tenant_id, "roles": auth.roles, "permissions": list(auth.permissions)}

@app.get("/perm-check")
def perm_check(auth: AuthContext = Depends(require_permission(PERM_ALERT_INGEST))):
    return {"status": "ok"}

client = TestClient(app)

class TestAuthMiddleware(unittest.TestCase):

    def setUp(self):
        self.secret = "test-secret"

    @patch('common.auth.middleware.get_config')
    def test_dev_mode_safe_defaults(self, mock_config):
        # Case: DEV_MODE=True, ALLOW_DEV_OVERRIDES=False
        mock_config.return_value = {
            "DEV_MODE": True,
            "ALLOW_DEV_OVERRIDES": False,
            "JWT_ALGORITHM": "HS256"
        }

        # Try to override
        headers = {"X-Dev-Tenant": "hacker-tenant"}
        resp = client.get("/protected", headers=headers)

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["tenant"], "dev-tenant") # Should be default
        self.assertIn(ROLE_ADMIN, data["roles"])
        self.assertIn(PERM_ALERT_INGEST, data["permissions"]) # Admin has all perms

    @patch('common.auth.middleware.get_config')
    def test_permissions_resolution(self, mock_config):
        # Case: JWT with ROLE_ANALYST
        mock_config.return_value = {
            "DEV_MODE": False,
            "JWT_SECRET": "secret",
            "JWT_ALGORITHM": "HS256",
            "OIDC_ISSUER": "issuer"
        }
        
        token = jwt.encode({
            "sub": "user1",
            "tenant_id": "tenant1",
            "roles": [ROLE_ANALYST],
            "iss": "issuer",
            "aud": "v5-core"
        }, "secret", algorithm="HS256")
        
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.get("/protected", headers=headers)
        
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn(PERM_ALERT_READ, data["permissions"])
        self.assertNotIn(PERM_ALERT_INGEST, data["permissions"])

    @patch('common.auth.middleware.get_config')
    def test_require_permission_success(self, mock_config):
        mock_config.return_value = {
            "DEV_MODE": False,
            "JWT_SECRET": "secret",
            "JWT_ALGORITHM": "HS256",
            "OIDC_ISSUER": "issuer"
        }
        # User with ADMIN role (has INGEST perm)
        token = jwt.encode({
            "sub": "user1",
            "tenant_id": "tenant1",
            "roles": [ROLE_ADMIN],
            "iss": "issuer",
            "aud": "v5-core"
        }, "secret", algorithm="HS256")
        
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.get("/perm-check", headers=headers)
        self.assertEqual(resp.status_code, 200)

    @patch('common.auth.middleware.get_config')
    def test_require_permission_fail(self, mock_config):
        mock_config.return_value = {
            "DEV_MODE": False,
            "JWT_SECRET": "secret",
            "JWT_ALGORITHM": "HS256",
            "OIDC_ISSUER": "issuer"
        }
        # User with ANALYST role (NO INGEST perm)
        token = jwt.encode({
            "sub": "user1",
            "tenant_id": "tenant1",
            "roles": [ROLE_ANALYST],
            "iss": "issuer",
            "aud": "v5-core"
        }, "secret", algorithm="HS256")
        
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.get("/perm-check", headers=headers)
        self.assertEqual(resp.status_code, 403)

if __name__ == "__main__":
    unittest.main()
