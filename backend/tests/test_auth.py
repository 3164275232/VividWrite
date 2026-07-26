import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from auth import (
    AUTH_COOKIE_NAME,
    configured_users,
    create_password_hash,
    create_session_token,
    read_session_token,
    verify_password_hash,
)
from main import app


class AuthenticationTests(unittest.TestCase):
    def test_password_hash_accepts_only_the_original_password(self):
        encoded = create_password_hash(
            "shared-test-password",
            salt=b"0123456789abcdef",
            iterations=1_000,
        )

        self.assertTrue(verify_password_hash("shared-test-password", encoded))
        self.assertFalse(verify_password_hash("wrong-password", encoded))
        self.assertFalse(verify_password_hash("shared-test-password", "invalid"))

    def test_signed_session_expires_and_rejects_tampering(self):
        environment = {
            "APP_AUTH_ENABLED": "true",
            "APP_TEST_USERS": "tester01,tester02",
            "APP_SESSION_SECRET": "a-test-secret-that-is-not-used-in-production",
            "APP_SESSION_TTL_SECONDS": "600",
        }
        with patch.dict(os.environ, environment, clear=False):
            token = create_session_token("tester01", now=1_000)

            self.assertEqual(read_session_token(token, now=1_001), "tester01")
            self.assertIsNone(read_session_token(token, now=1_600))
            self.assertIsNone(read_session_token(f"{token}changed", now=1_001))

    def test_removed_user_cannot_reuse_an_old_session(self):
        environment = {
            "APP_AUTH_ENABLED": "true",
            "APP_TEST_USERS": "tester01",
            "APP_SESSION_SECRET": "a-test-secret-that-is-not-used-in-production",
        }
        with patch.dict(os.environ, environment, clear=False):
            token = create_session_token("tester01", now=1_000)
            os.environ["APP_TEST_USERS"] = "tester02"

            self.assertIsNone(read_session_token(token, now=1_001))
            self.assertEqual(configured_users(), {"tester02"})

    def test_login_cookie_unlocks_protected_api_routes(self):
        environment = {
            "APP_AUTH_ENABLED": "true",
            "APP_TEST_USERS": "tester01,tester02",
            "APP_SHARED_PASSWORD_HASH": create_password_hash(
                "shared-test-password",
                iterations=1_000,
            ),
            "APP_SESSION_SECRET": "a-test-secret-that-is-not-used-in-production",
            "APP_COOKIE_SECURE": "false",
        }
        headers = {"x-real-ip": "192.0.2.10"}

        with patch.dict(os.environ, environment, clear=False):
            client = TestClient(app)

            self.assertEqual(
                client.post("/api/next-sentence", json={}, headers=headers).status_code,
                401,
            )
            self.assertEqual(
                client.post(
                    "/api/auth/login",
                    json={"username": "tester01", "password": "wrong"},
                    headers=headers,
                ).status_code,
                401,
            )

            login_response = client.post(
                "/api/auth/login",
                json={
                    "username": "tester01",
                    "password": "shared-test-password",
                },
                headers=headers,
            )
            self.assertEqual(login_response.status_code, 200)
            self.assertIn(AUTH_COOKIE_NAME, client.cookies)

            current_user_response = client.get("/api/auth/me", headers=headers)
            self.assertEqual(current_user_response.status_code, 200)
            self.assertEqual(current_user_response.json()["username"], "tester01")

            logout_response = client.post("/api/auth/logout", headers=headers)
            self.assertEqual(logout_response.status_code, 200)
            self.assertEqual(client.get("/api/auth/me", headers=headers).status_code, 401)


if __name__ == "__main__":
    unittest.main()
