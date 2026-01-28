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
    payment_detail: Optional[Any] = None
    link_page_url: Optional[str] = None
    external_id: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None


def build_external_id(chat_id: int, plan: str) -> str:
    # tg-<chat_id>-<plan>-<uuid>
    return f"tg-{chat_id}-{plan}-{uuid.uuid4().hex}"


def _clean_base_url(value: str) -> str:
    v = (value or "").strip()
    # Remove accidental quotes from env values
    if (len(v) >= 2) and ((v[0] == v[-1]) and v[0] in {"'", '"'}):
        v = v[1:-1].strip()
    return v.rstrip("/")


class PaysharkClient:
    def __init__(self) -> None:
        self.base_url = _clean_base_url(os.getenv("PAYSHARK_BASE_URL") or "https://app.payshark.io")
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

        self._timeout = float(os.getenv("PAYSHARK_TIMEOUT_SEC", "25"))

    def _headers(self) -> Dict[str, str]:
        # В рабочем примере Payshark: только Access-Token
        return {
            "Accept": "application/json",
            "Access-Token": self.access_token,
        }

    async def create_h2h_order(
        self,
        *,
        amount: int,
        external_id: str,
        payment_detail_type: str = "card",
        # Для режима "любой банк" gateway НЕ передаём, а указываем currency=rub
        currency: Optional[str] = None,
        payment_gateway: Optional[str] = None,
        description: str = "",
    ) -> PaysharkOrder:
        """Host2Host (H2H): POST /api/h2h/order (как в примере curl Payshark).

        Минимум полей:
        - merchant_id
        - external_id
        - amount
        - payment_detail_type
        Дополнительно:
        - payment_gateway (если хотите конкретный банк)
        - currency (если хотите "любой банк", например rub)
        """

        url = f"{self.base_url}/api/h2h/order"

        data: Dict[str, Any] = {
            "merchant_id": self.merchant_id,
            "external_id": str(external_id),
            "amount": int(amount),
            "payment_detail_type": (payment_detail_type or "card").strip(),
        }

        gw = (payment_gateway or "").strip()
        if gw:
            data["payment_gateway"] = gw

        cur = (currency or "").strip()
        if cur:
            data["currency"] = cur

        if description:
            data["description"] = str(description)

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            # как в примере curl: -d ... (application/x-www-form-urlencoded)
            r = await client.post(url, headers=self._headers(), data=data)

        # Payshark часто возвращает JSON даже на ошибке
        try:
            payload = r.json()
        except Exception:
            payload = None

        if r.status_code >= 400:
            # Сохраняем оригинальный текст (там message на русском)
            raise RuntimeError(f"Payshark H2H HTTP {r.status_code}: {r.text[:1200]}")

        if isinstance(payload, dict) and payload.get("success") is False:
            msg = str(payload.get("message") or "Unknown error")
            raise RuntimeError(f"Payshark H2H error: {msg}")

        obj = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload
        if not isinstance(obj, dict):
            raise RuntimeError(f"Unexpected Payshark H2H response: {r.text[:1200]}")

        order_id = str(obj.get("order_id") or obj.get("id") or "")
        if not order_id:
            raise RuntimeError(f"Payshark H2H response missing order_id: {r.text[:1200]}")

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
            currency=str(obj.get("currency") or (currency or "")),
            payment_detail=payment_detail,
            link_page_url=str(link) if link else None,
            external_id=str(obj.get("external_id") or external_id),
            raw=obj,
        )
