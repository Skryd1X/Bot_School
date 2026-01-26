import os
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx


@dataclass
class PaysharkOrder:
    order_id: str
    status: str
    amount: str
    currency: str
    # For H2H flow this is usually the requisites / details the user must pay to.
    # Can be a dict, string, etc. We keep it raw.
    payment_detail: Optional[Any] = None
    link_page_url: Optional[str] = None
    external_id: Optional[str] = None
    client_id: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None


def build_external_id(chat_id: int, plan: str) -> str:
    # tg-<chat_id>-<plan>-<uuid>
    return f"tg-{chat_id}-{plan}-{uuid.uuid4().hex}"


class PaysharkClient:
    def __init__(self) -> None:
        self.base_url = (os.getenv("PAYSHARK_BASE_URL") or "").rstrip("/")
        self.access_token = (
            os.getenv("PAYSHARK_ACCESS_TOKEN")
            or os.getenv("PAYSHARK_TOKEN")
            or os.getenv("PAYSHARK_API_TOKEN")
            or os.getenv("ACCESS_TOKEN")
            or ""
        ).strip()
        self.merchant_id = (
            os.getenv("PAYSHARK_MERCHANT_ID")
            or os.getenv("PAYSHARK_MERCHANT")
            or os.getenv("MERCHANT_ID")
            or ""
        ).strip()

        if not self.base_url:
            raise RuntimeError("PAYSHARK_BASE_URL is not set")
        if not self.access_token:
            raise RuntimeError("PAYSHARK_ACCESS_TOKEN is not set")
        if not self.merchant_id:
            raise RuntimeError("PAYSHARK_MERCHANT_ID is not set")

        self._timeout = float(os.getenv("PAYSHARK_TIMEOUT_SEC", "20"))

    def _headers(self) -> Dict[str, str]:
        # Different Payshark docs/screens may show different auth headers.
        # We send both common variants to maximize compatibility.
        return {
            "Accept": "application/json",
            "access-token": self.access_token,
            "Authorization": f"Bearer {self.access_token}",
        }

    async def create_order(
        self,
        *,
        amount: str,
        currency: str,
        external_id: str,
        client_id: str,
        callback_url: str,
        manually: int = 1,
        description: str = "",
    ) -> PaysharkOrder:
        url = f"{self.base_url}/api/merchant/order"

        # Send as form-encoded (matches their curl style)
        data = {
            "merchant_id": self.merchant_id,
            "amount": str(amount),
            "currency": str(currency),
            "external_id": external_id,
            "client_id": str(client_id),
            "callback_url": callback_url,
            "manually": str(int(manually)),
        }
        if description:
            data["description"] = description

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(url, headers=self._headers(), data=data)
            r.raise_for_status()
            payload = r.json()

        obj = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload
        if not isinstance(obj, dict):
            raise RuntimeError(f"Unexpected Payshark response: {payload!r}")

        order_id = str(obj.get("order_id") or obj.get("id") or "")
        if not order_id:
            raise RuntimeError(f"Payshark response missing order_id: {payload!r}")

        link = obj.get("link_page_url") or obj.get("payment_link") or obj.get("url")

        return PaysharkOrder(
            order_id=order_id,
            status=str(obj.get("status") or ""),
            amount=str(obj.get("amount") or amount),
            currency=str(obj.get("currency") or currency),
            payment_detail=obj.get("payment_detail") if isinstance(obj, dict) else None,
            link_page_url=str(link) if link else None,
            external_id=str(obj.get("external_id") or external_id),
            client_id=str(obj.get("client_id") or client_id),
            raw=obj,
        )

    async def create_h2h_order(
        self,
        *,
        amount: str,
        currency: str,
        external_id: str,
        callback_url: str,
        client_id: str,
        description: str = "",
    ) -> PaysharkOrder:
        """Create a Host2Host (H2H) order.

        Payshark H2H expects creating a deal via POST /api/h2h/order.
        Their implementations vary a bit, so we:
        - send both snake_case and camelCase keys
        - default to JSON body (can be forced to form via PAYSHARK_H2H_BODY=form)
        - parse response defensively
        """

        url = f"{self.base_url}/api/h2h/order"

        data: Dict[str, Any] = {
            # snake_case
            "merchant_id": self.merchant_id,
            "amount": str(amount),
            "currency": str(currency),
            "external_id": str(external_id),
            "callback_url": str(callback_url),
            "client_id": str(client_id),
            # camelCase fallbacks (usually ignored if not needed)
            "merchantId": self.merchant_id,
            "externalId": str(external_id),
            "callbackUrl": str(callback_url),
            "clientId": str(client_id),
        }
        if description:
            data["description"] = str(description)

        body_mode = (os.getenv("PAYSHARK_H2H_BODY") or "json").strip().lower()

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            if body_mode == "form":
                r = await client.post(url, headers=self._headers(), data=data)
            else:
                r = await client.post(url, headers=self._headers(), json=data)

        # Try to decode JSON even for non-2xx responses.
        try:
            payload = r.json()
        except Exception:
            payload = {"raw_text": r.text}

        if r.status_code >= 400:
            raise RuntimeError(f"Payshark H2H HTTP {r.status_code}: {r.text[:1200]}")

        obj = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload
        if not isinstance(obj, dict):
            raise RuntimeError(f"Unexpected Payshark H2H response: {payload!r}")

        order_id = str(obj.get("order_id") or obj.get("id") or "")
        if not order_id:
            raise RuntimeError(f"Payshark H2H response missing order_id: {payload!r}")

        link = obj.get("link_page_url") or obj.get("payment_link") or obj.get("url")
        payment_detail = (
            obj.get("payment_detail")
            or obj.get("paymentDetails")
            or obj.get("requisites")
            or obj.get("requisite")
            or obj.get("details")
        )

        return PaysharkOrder(
            order_id=order_id,
            status=str(obj.get("status") or ""),
            amount=str(obj.get("amount") or amount),
            currency=str(obj.get("currency") or currency),
            payment_detail=payment_detail,
            link_page_url=str(link) if link else None,
            external_id=str(obj.get("external_id") or external_id),
            client_id=str(obj.get("client_id") or client_id),
            raw=obj,
        )

    async def get_order(self, order_id: str) -> PaysharkOrder:
        url = f"{self.base_url}/api/merchant/order/{order_id}"

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.get(url, headers=self._headers())
            r.raise_for_status()
            payload = r.json()

        obj = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload
        if not isinstance(obj, dict):
            raise RuntimeError(f"Unexpected Payshark response: {payload!r}")

        return PaysharkOrder(
            order_id=str(obj.get("order_id") or obj.get("id") or order_id),
            status=str(obj.get("status") or ""),
            amount=str(obj.get("amount") or ""),
            currency=str(obj.get("currency") or ""),
            payment_detail=obj.get("payment_detail") if isinstance(obj, dict) else None,
            link_page_url=str(obj.get("link_page_url") or obj.get("payment_link") or obj.get("url") or "") or None,
            external_id=str(obj.get("external_id") or "") or None,
            client_id=str(obj.get("client_id") or "") or None,
            raw=obj,
        )

    async def get_h2h_order(self, order_id: str) -> PaysharkOrder:
        url = f"{self.base_url}/api/h2h/order/{order_id}"

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.get(url, headers=self._headers())
            r.raise_for_status()
            payload = r.json()

        obj = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload
        if not isinstance(obj, dict):
            raise RuntimeError(f"Unexpected Payshark H2H response: {payload!r}")

        link = obj.get("link_page_url") or obj.get("payment_link") or obj.get("url")
        payment_detail = (
            obj.get("payment_detail")
            or obj.get("paymentDetails")
            or obj.get("requisites")
            or obj.get("requisite")
            or obj.get("details")
        )

        return PaysharkOrder(
            order_id=str(obj.get("order_id") or obj.get("id") or order_id),
            status=str(obj.get("status") or ""),
            amount=str(obj.get("amount") or ""),
            currency=str(obj.get("currency") or ""),
            payment_detail=payment_detail,
            link_page_url=str(link) if link else None,
            external_id=str(obj.get("external_id") or "") or None,
            client_id=str(obj.get("client_id") or "") or None,
            raw=obj,
        )
