import unittest
from unittest.mock import MagicMock, patch
import os
import sys
import pytest

# Add common to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from common.auth.middleware import validate_auth_config

class TestStartupGuardrail(unittest.TestCase):

    @patch('common.auth.middleware.get_config')
    def test_startup_fails_rs256_no_key(self, mock_config):
        # Simulate insecure config
        mock_config.return_value = {
            "JWT_ALGORITHM": "RS256",
            "JWKS_URL": "",
            "JWT_SECRET": "",
            "DEV_MODE": False
        }

        with self.assertRaises(RuntimeError) as cm:
            validate_auth_config()
        self.assertIn("CRITICAL: RS256 requires JWKS/PublicKey", str(cm.exception))

    @patch('common.auth.middleware.get_config')
    def test_startup_passes_hs256(self, mock_config):
        # Simulate valid HS256 config
        mock_config.return_value = {
            "JWT_ALGORITHM": "HS256",
            "JWKS_URL": "",
            "JWT_SECRET": "some-secret",
            "DEV_MODE": False
        }
        # Should not raise
        validate_auth_config()

if __name__ == "__main__":
    unittest.main()
