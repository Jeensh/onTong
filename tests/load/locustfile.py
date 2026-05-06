"""Locust load scenario for onTong wiki rename/save mix.

Usage:
    locust -f tests/load/locustfile.py --host http://localhost:8002 \
           --users 50 --spawn-rate 5 --run-time 60s --headless
"""
from __future__ import annotations

import json
import random
import urllib.parse
from locust import HttpUser, task, between, events


SEED_FOLDER = "load_test_demo"
USER_IDS = ["donghae", "kim", "lee"]


def _random_doc(seed_count: int = 1000) -> str:
    idx = random.randrange(seed_count)
    return f"{SEED_FOLDER}/doc_{idx:05d}.md"


class WikiLoadUser(HttpUser):
    wait_time = between(0.5, 2.0)

    def on_start(self):
        self.user_id = random.choice(USER_IDS)
        # Capture baseVersion for save scenarios — fetch one doc to seed cache
        self.headers = {"X-User-Id": self.user_id}

    @task(70)
    def read_random_doc(self):
        path = _random_doc()
        with self.client.get(
            f"/api/wiki/file/{urllib.parse.quote(path, safe='')}",
            headers=self.headers,
            name="GET /file",
            catch_response=True,
        ) as r:
            if r.status_code in (200, 404):
                r.success()
            else:
                r.failure(f"HTTP {r.status_code}")

    @task(20)
    def save_random_doc(self):
        path = _random_doc()
        # First fetch to get ETag
        with self.client.get(
            f"/api/wiki/file/{urllib.parse.quote(path, safe='')}",
            headers=self.headers,
            name="GET /file (for save)",
            catch_response=True,
        ) as r:
            if r.status_code != 200:
                r.success()  # 404 is acceptable, just skip
                return
            etag = r.headers.get("etag", "").strip('"')
            try:
                content = r.json().get("raw_content", "")
            except Exception:
                return
        # Append a tiny suffix
        new_content = content.rstrip() + f"\n\n<!-- load test {random.randint(0, 1_000_000)} -->\n"
        save_headers = {**self.headers, "Content-Type": "application/json"}
        if etag:
            save_headers["If-Match"] = f'"{etag}"'
        with self.client.put(
            f"/api/wiki/file/{urllib.parse.quote(path, safe='')}",
            data=json.dumps({"content": new_content}),
            headers=save_headers,
            name="PUT /file",
            catch_response=True,
        ) as r:
            if r.status_code in (200, 409):
                r.success()  # 409 is expected occasionally
            else:
                r.failure(f"HTTP {r.status_code}")

    @task(5)
    def rename_random_doc(self):
        old_path = _random_doc()
        idx = random.randrange(1_000_000)
        new_path = f"{SEED_FOLDER}/renamed_{idx:08d}.md"
        with self.client.patch(
            f"/api/wiki/file/{urllib.parse.quote(old_path, safe='')}",
            data=json.dumps({"new_path": new_path}),
            headers={**self.headers, "Content-Type": "application/json"},
            name="PATCH /file (rename)",
            catch_response=True,
        ) as r:
            if r.status_code in (200, 404, 409):
                r.success()
            else:
                r.failure(f"HTTP {r.status_code}")

    @task(5)
    def broken_refs_query(self):
        with self.client.get(
            "/api/wiki/broken-refs?limit=20",
            headers=self.headers,
            name="GET /broken-refs",
            catch_response=True,
        ) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"HTTP {r.status_code}")
