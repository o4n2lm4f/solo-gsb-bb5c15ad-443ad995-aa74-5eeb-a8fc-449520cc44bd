"""End-to-end API tests.

Requires fastapi/uvicorn/httpx (installed in the Docker image or via
``pip install -r requirements-dev.txt``). Skipped automatically when the
dependencies are unavailable, so the pure-logic suites still run anywhere.
"""

from __future__ import annotations

import unittest

try:
    from fastapi.testclient import TestClient

    from app.main import app
except ImportError:  # pragma: no cover - exercised only without deps
    TestClient = None


@unittest.skipIf(TestClient is None, "fastapi/httpx not installed")
class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_precheck_end_to_end(self):
        payload = {
            "entries": [
                {"path": "docs/README.md", "type": "file"},
                {"path": "DOCS\\readme.md", "type": "file"},
                {"path": "C:\\evil\\abs.txt", "type": "file"},
                {"path": "../escape.txt", "type": "file"},
                {"path": "dir", "type": "file"},
                {"path": "dir/child.txt", "type": "file"},
                {"path": "CON.txt", "type": "file"},
            ]
        }
        response = self.client.post("/precheck", json=payload)
        self.assertEqual(response.status_code, 200)
        body = response.json()

        # Per-entry results keep the input order.
        self.assertEqual([r["index"] for r in body["results"]], list(range(7)))
        self.assertEqual(body["results"][0]["canonical_path"], "docs\\readme.md")
        self.assertEqual(body["results"][1]["canonical_path"], "docs\\readme.md")
        self.assertFalse(body["results"][2]["safe"])
        self.assertIn("drive_letter_path", body["results"][2]["issues"])
        self.assertFalse(body["results"][3]["safe"])
        self.assertIn("parent_escape", body["results"][3]["issues"])
        self.assertIn("reserved_device_name", body["results"][6]["issues"])

        # Case/separator variants collide.
        self.assertIn(
            {"canonical_path": "docs\\readme.md", "indices": [0, 1]},
            body["collisions"],
        )

        # File "dir" blocks the entry beneath it.
        self.assertIn(
            {"file_index": 4, "canonical_path": "dir", "blocked_indices": [5]},
            body["hierarchy_conflicts"],
        )

    def test_empty_batch(self):
        response = self.client.post("/precheck", json={"entries": []})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"results": [], "collisions": [], "hierarchy_conflicts": []},
        )

    def test_invalid_type_rejected(self):
        response = self.client.post(
            "/precheck", json={"entries": [{"path": "a", "type": "symlink"}]}
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
