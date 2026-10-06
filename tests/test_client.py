"""Offline tests: the HTTP session is mocked, no API key or network needed.

Run with:  python -m unittest discover -s tests
"""

import unittest
from unittest import mock

from nexwall import NexWallClient, RateLimitError
from nexwall.cli import main


def fake_response(status=200, body=None, headers=None):
    response = mock.Mock()
    response.status_code = status
    response.ok = 200 <= status < 300
    response.reason = "Too Many Requests" if status == 429 else "OK"
    response.headers = headers or {}
    response.json.return_value = body if body is not None else {}
    return response


class ClientTests(unittest.TestCase):
    def make_client(self, response):
        session = mock.Mock()
        session.get.return_value = response
        return NexWallClient(api_key="test-key", session=session), session

    def test_random_sends_auth_and_tracks_quota(self):
        body = {
            "data": [{"id": 7, "image_url": "https://example.com/7.jpg", "resolution": "3840x2160"}],
            "current_page": 1,
            "last_page": 9,
            "per_page": 1,
            "total": 9,
            "plan": "free",
            "remaining_requests_today": 98,
        }
        client, session = self.make_client(fake_response(body=body))

        wallpaper = client.random(category_id=5)

        self.assertEqual(wallpaper["id"], 7)
        self.assertEqual(client.remaining_today, 98)
        self.assertEqual(client.plan, "free")
        _, kwargs = session.get.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(kwargs["params"], {"page": 1, "per_page": 1, "category_id": 5, "type": "image", "sort": "random"})

    def test_429_raises_rate_limit_error(self):
        client, _ = self.make_client(
            fake_response(429, {"message": "Daily quota exceeded"}, {"Retry-After": "3600"})
        )
        with self.assertRaises(RateLimitError) as ctx:
            client.categories()
        self.assertEqual(ctx.exception.retry_after, 3600)
        self.assertEqual(client.remaining_today, 0)

    def test_cli_returns_2_on_rate_limit(self):
        with mock.patch("nexwall.client.requests.Session") as session_cls, mock.patch("sys.stderr"):
            session_cls.return_value.get.return_value = fake_response(429, {"message": "quota"})
            self.assertEqual(main(["categories", "--api-key", "x"]), 2)


if __name__ == "__main__":
    unittest.main()
