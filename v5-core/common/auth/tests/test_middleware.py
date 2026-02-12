import unittest
from unittest.mock import MagicMock, patch
import os
import sys
import jwt
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

# Add common to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# Need to patch BEFORE importing middleware to affect config (if global) OR patch get_config
# Since we moved config to get_config(), we can patch 'common.auth.middleware.get_config'

from common.auth import middleware
from common.auth.middleware import get_auth_context, require_role, AuthContext

app = FastAPI()

@app.get("/protected")
def protected_endpoint(auth: AuthContext = Depends(get_auth_context)):
    return {"user": auth.user_id, "tenant": auth.tenant_id, "roles": auth.roles}

@app.get("/admin")
def admin_endpoint(auth: AuthContext = Depends(require_role(["SYSTEM_ADMIN"]))):
    return {"status": "admin_access"}

client = TestClient(app)

class TestAuthMiddleware(unittest.TestCase):

    def setUp(self):
        self.secret = "test-secret"
        self.valid_token = jwt.encode(
            {"sub": "user1", "tenant_id": "tenant1", "roles": ["SOC_ANALYST"], "aud": "v5-core", "iss": "https://auth.example.com"},
            self.secret, algorithm="HS256"
        )

    def tearDown(self):
        pass

    @patch('common.auth.middleware.get_config')
    def test_dev_mode_headers(self, mock_config):
        mock_config.return_value = {"DEV_MODE": True}

        # Test override
        headers = {"X-Dev-Tenant": "dev-tenant-custom", "X-Dev-User": "dev-user-custom"}
        resp = client.get("/protected", headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["tenant"], "dev-tenant-custom")

    @patch('common.auth.middleware.get_config')
    def test_prod_mode_ignores_dev_headers(self, mock_config):
        mock_config.return_value = {
            "DEV_MODE": False,
            "JWT_SECRET": self.secret,
            "JWT_ALGORITHM": "HS256",
            "OIDC_ISSUER": "https://auth.example.com",
            "JWKS_URL": ""
        }

        # Valid token but trying to override tenant via header
        headers = {"Authorization": f"Bearer {self.valid_token}", "X-Dev-Tenant": "hacker-tenant"}
        resp = client.get("/protected", headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["tenant"], "tenant1") # Should ignore header and use token

    @patch('common.auth.middleware.get_config')
    def test_missing_claims(self, mock_config):
        mock_config.return_value = {
            "DEV_MODE": False,
            "JWT_SECRET": self.secret,
            "JWT_ALGORITHM": "HS256",
            "OIDC_ISSUER": "https://auth.example.com",
            "JWKS_URL": ""
        }

        # Missing tenant_id
        token = jwt.encode({"sub": "user1", "aud": "v5-core", "iss": "https://auth.example.com"}, self.secret, algorithm="HS256")
        resp = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status_code, 403) # Forbidden if no tenant

    @patch('common.auth.middleware.get_config')
    def test_roles_normalization(self, mock_config):
        mock_config.return_value = {
            "DEV_MODE": False,
            "JWT_SECRET": self.secret,
            "JWT_ALGORITHM": "HS256",
            "OIDC_ISSUER": "https://auth.example.com",
            "JWKS_URL": ""
        }

        # Roles as string
        token = jwt.encode(
            {"sub": "user1", "tenant_id": "t1", "roles": "SOC_ANALYST", "aud": "v5-core", "iss": "https://auth.example.com"},
            self.secret, algorithm="HS256"
        )
        resp = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status_code, 200)
        roles = resp.json()["roles"]
        self.assertTrue(isinstance(roles, list))
        self.assertEqual(roles, ["SOC_ANALYST"])

    @patch('common.auth.middleware.get_config')
    def test_require_role_dependency(self, mock_config):
        mock_config.return_value = {
            "DEV_MODE": False,
            "JWT_SECRET": self.secret,
            "JWT_ALGORITHM": "HS256",
            "OIDC_ISSUER": "https://auth.example.com",
            "JWKS_URL": ""
        }

        # User has SOC_ANALYST, endpoint needs SYSTEM_ADMIN
        resp = client.get("/admin", headers={"Authorization": f"Bearer {self.valid_token}"})
        self.assertEqual(resp.status_code, 403)

        # Admin User
        admin_token = jwt.encode(
            {"sub": "admin", "tenant_id": "t1", "roles": ["SYSTEM_ADMIN"], "aud": "v5-core", "iss": "https://auth.example.com"},
            self.secret, algorithm="HS256"
        )
        resp = client.get("/admin", headers={"Authorization": f"Bearer {admin_token}"})
        self.assertEqual(resp.status_code, 200)

if __name__ == "__main__":
    unittest.main()
