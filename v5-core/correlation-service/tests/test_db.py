import unittest
import os
import sys
from unittest.mock import patch, MagicMock

# Add app to path - relying on main.py fix or just manual append for safety in this isolated test
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../app')))
# And common
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../common')))

from db import Database
from config import secrets

class TestDatabaseConfig(unittest.TestCase):

    def setUp(self):
        # Clear env vars
        self.env_vars_to_clear = ['POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_DB']
        self.old_env = {}
        for key in self.env_vars_to_clear:
            self.old_env[key] = os.environ.get(key)
            if key in os.environ:
                del os.environ[key]

    def tearDown(self):
        # Restore env vars
        for key, value in self.old_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]

    @patch('psycopg2.connect')
    def test_init_fails_without_credentials(self, mock_connect):
        # Should raise RuntimeError because POSTGRES_USER is required
        with self.assertRaises(RuntimeError) as cm:
            Database()
        self.assertIn("Missing required secret: POSTGRES_USER", str(cm.exception))

    @patch('psycopg2.connect')
    def test_init_fails_without_password(self, mock_connect):
        os.environ['POSTGRES_USER'] = 'testuser'
        # Should raise RuntimeError because POSTGRES_PASSWORD is required
        with self.assertRaises(RuntimeError) as cm:
            Database()
        self.assertIn("Missing required secret: POSTGRES_PASSWORD", str(cm.exception))

    @patch('psycopg2.connect')
    def test_init_succeeds_with_credentials(self, mock_connect):
        os.environ['POSTGRES_USER'] = 'testuser'
        os.environ['POSTGRES_PASSWORD'] = 'testpass'

        db = Database()

        self.assertEqual(db.user, 'testuser')
        self.assertEqual(db.password, 'testpass')
        self.assertEqual(db.host, 'postgres') # Default
        self.assertEqual(db.port, 5432) # Default

    @patch('psycopg2.connect')
    def test_init_overrides_defaults(self, mock_connect):
        os.environ['POSTGRES_USER'] = 'testuser'
        os.environ['POSTGRES_PASSWORD'] = 'testpass'
        os.environ['POSTGRES_HOST'] = 'myhost'
        os.environ['POSTGRES_PORT'] = '9999'

        db = Database()

        self.assertEqual(db.host, 'myhost')
        self.assertEqual(db.port, 9999)

if __name__ == '__main__':
    unittest.main()
