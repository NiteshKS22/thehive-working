import unittest
from unittest.mock import MagicMock, patch
import os
import sys
import jwt
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

# Add common to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from common.auth import middleware
from common.auth.middleware import get_auth_context, require_role, AuthContext

app = FastAPI()

@app.get("/protected")
def protected_endpoint(auth: AuthContext = Depends(get_auth_context)):
    return {"user": auth.user_id, "tenant": auth.tenant_id, "roles": auth.roles}

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
        self.assertEqual(resp.json()["tenant"], "dev-tenant") # Should be default
        self.assertNotEqual(resp.json()["tenant"], "hacker-tenant")

    @patch('common.auth.middleware.get_config')
    def test_dev_mode_overrides_allowed(self, mock_config):
        # Case: DEV_MODE=True, ALLOW_DEV_OVERRIDES=True
        mock_config.return_value = {
            "DEV_MODE": True,
            "ALLOW_DEV_OVERRIDES": True,
            "JWT_ALGORITHM": "HS256"
        }

        headers = {"X-Dev-Tenant": "custom-tenant"}
        resp = client.get("/protected", headers=headers)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["tenant"], "custom-tenant")

if __name__ == "__main__":
    unittest.main()
