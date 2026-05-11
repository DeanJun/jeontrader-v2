from __future__ import annotations

import time

import httpx

PAPER_BASE_URL = "https://openapivts.koreainvestment.com:29443"
REAL_BASE_URL  = "https://openapi.koreainvestment.com:9443"


class KISAuth:
    def __init__(
        self,
        mode: str,
        app_key: str,
        app_secret: str,
    ) -> None:
        self.mode = mode
        self.app_key = app_key
        self.app_secret = app_secret
        self.base_url = PAPER_BASE_URL if mode == "paper" else REAL_BASE_URL
        self._token: str = ""
        self._expires_at: float = 0.0
        self.client: httpx.AsyncClient = httpx.AsyncClient(timeout=30.0)

    async def get_token(self) -> str:
        if self._token and time.monotonic() < self._expires_at:
            return self._token
        await self._refresh()
        return self._token

    async def _refresh(self) -> None:
        resp = await self.client.post(
            f"{self.base_url}/oauth2/tokenP",
            json={
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "appsecret": self.app_secret,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        self._token = data["access_token"]
        expires_in = int(data.get("expires_in", 86400))
        self._expires_at = time.monotonic() + expires_in - 300
        print(f"[KIS] token refreshed (mode={self.mode})")

    def build_headers(self, tr_id: str, token: str) -> dict:
        return {
            "Authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
            "tr_cont": "",
            "custtype": "P",
            "Content-Type": "application/json",
        }
