import os
import datetime as dt
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx


@dataclass
class WataPaymentLink:
    id: str
    status: str
    url: str
    amount: float
    currency: str
    order_id: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None


class WataClient:
    def __init__(self) -> None:
        self.base_url = (os.getenv("WATA_BASE_URL") or "https://api.wata.pro/api/h2h").rstrip("/")
        self.access_token = (os.getenv("WATA_ACCESS_TOKEN") or "").strip()
        if not self.access_token:
            raise RuntimeError("WATA_ACCESS_TOKEN is not set")

        self._timeout = float(os.getenv("WATA_TIMEOUT_SEC", "60"))

        self.default_currency = (os.getenv("WATA_CURRENCY") or "RUB").strip().upper()
        self.default_type = (os.getenv("WATA_LINK_TYPE") or "OneTime").strip()
        self.ttl_min = int(os.getenv("WATA_LINK_TTL_MIN", "0") or "0")

        self.success_url = (os.getenv("WATA_SUCCESS_URL") or "").strip() or None
        self.fail_url = (os.getenv("WATA_FAIL_URL") or "").strip() or None

    def _headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }

    async def create_payment_link(
        self,
        *,
        amount: float,
        currency: Optional[str] = None,
        order_id: Optional[str] = None,
        description: str = "",
        success_redirect_url: Optional[str] = None,
        fail_redirect_url: Optional[str] = None,
        link_type: Optional[str] = None,
        ttl_min: Optional[int] = None,
    ) -> WataPaymentLink:
        url = f"{self.base_url}/links"

        payload: Dict[str, Any] = {
            "type": (link_type or self.default_type or "OneTime"),
            "amount": float(amount),
            "currency": (currency or self.default_currency or "RUB"),
        }

        if order_id:
            payload["orderId"] = str(order_id)

        if description:
            payload["description"] = str(description)

        s_url = success_redirect_url or self.success_url
        f_url = fail_redirect_url or self.fail_url

        if s_url:
            payload["successRedirectUrl"] = str(s_url)
        if f_url:
            payload["failRedirectUrl"] = str(f_url)

        ttl = self.ttl_min if ttl_min is None else int(ttl_min)
        if ttl and ttl > 0:
            exp = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=ttl)
            payload["expirationDateTime"] = exp.isoformat().replace("+00:00", "Z")

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(url, headers=self._headers(), json=payload)

        try:
            data = r.json()
        except Exception:
            raise RuntimeError(f"WATA HTTP {r.status_code}: {r.text[:1200]}")

        if r.status_code >= 400:
            raise RuntimeError(f"WATA HTTP {r.status_code}: {data!r}")

        if not isinstance(data, dict) or not data.get("id") or not data.get("url"):
            raise RuntimeError(f"Unexpected WATA response: {data!r}")

        return WataPaymentLink(
            id=str(data.get("id")),
            status=str(data.get("status") or ""),
            url=str(data.get("url")),
            amount=float(data.get("amount") or amount),
            currency=str(data.get("currency") or (currency or self.default_currency)),
            order_id=str(data.get("orderId") or order_id) if (data.get("orderId") or order_id) else None,
            raw=data,
        )