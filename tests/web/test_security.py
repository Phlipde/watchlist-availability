"""Route tests: upload limit and cross-site writes."""

import io


class TestUploadLimit:
    def test_too_large_upload_is_rejected(self, client, monkeypatch):
        client.application.config["MAX_CONTENT_LENGTH"] = 100
        upload = {"backup": (io.BytesIO(b"x" * 1000), "backup.json")}
        answer = client.post("/api/backup", data=upload, content_type="multipart/form-data")
        assert answer.status_code == 413 and "too large" in answer.get_json()["error"]


class TestCrossSiteWrites:
    def _backup(self):
        return {"backup": (io.BytesIO(b'{"version": 1}'), "backup.json")}

    def test_other_site_cannot_post(self, client, store):
        for headers in (
            {"Origin": "https://evil.example"},
            {"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.example"},
            {"Sec-Fetch-Site": "same-site", "Origin": "http://localhost:8080"},
        ):
            answer = client.post("/api/backup", data=self._backup(), headers=headers)
            assert answer.status_code == 403, headers
        assert (
            client.put("/api/settings", json={"country": "GB"}, headers={"Origin": "null"}).status_code == 403
        )
        assert (
            client.delete("/api/favorites/1", headers={"Origin": "https://evil.example"}).status_code == 403
        )

    def test_own_page_and_tools_without_browser_headers_may_post(self, client):
        own = {"Origin": "http://localhost", "Sec-Fetch-Site": "same-origin"}
        assert client.post("/api/backup", data=self._backup(), headers=own).status_code == 200
        assert (
            client.post(
                "/api/backup", data=self._backup(), headers={"Origin": "http://localhost"}
            ).status_code
            == 200
        )
        assert client.post("/api/backup", data=self._backup()).status_code == 200  # curl, CLI, Home Assistant
        # Reading stays possible from anywhere; the browser keeps the answer from other sites.
        assert client.get("/api/settings", headers={"Origin": "https://evil.example"}).status_code == 200

    def test_reverse_proxy_host(self, client, monkeypatch):
        proxied = {"Origin": "https://watch.example.org"}
        assert client.post("/api/backup", data=self._backup(), headers=proxied).status_code == 403
        forwarded = {**proxied, "X-Forwarded-Host": "watch.example.org"}
        assert client.post("/api/backup", data=self._backup(), headers=forwarded).status_code == 200
        monkeypatch.setenv("WATCHLIST_TRUSTED_HOSTS", "other.example, watch.example.org")
        assert client.post("/api/backup", data=self._backup(), headers=proxied).status_code == 200
