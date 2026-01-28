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
        # В доке: Access-Token. На всякий — шлём несколько вариантов.
        return {
            "Accept": "application/json",
            "Access-Token": self.access_token,
            "access-token": self.access_token,
            "Authorization": f"Bearer {self.access_token}",
        }

    async def create_h2h_order(
        self,
        *,
        amount: int,
        external_id: str,
        payment_gateway: Optional[str] = None,
        payment_detail_type: Optional[str] = None,
        currency: Optional[str] = None,
        description: str = "",
    ) -> PaysharkOrder:
        """Host2Host (H2H): POST /api/h2h/order (по доке Payshark).

        Док-минимум полей:
        - merchant_id
        - external_id
        - amount (целое число)
        - payment_detail_type (пример: card)
        - payment_gateway (пример: sberbank) **или** currency (пример: rub) — для режима «любой банк»
        """

        url = f"{self.base_url}/api/h2h/order"

        # Если payment_gateway НЕ передан — можно работать в режиме «любой банк» через currency=rub.
        gateway = (payment_gateway or os.getenv("PAYSHARK_PAYMENT_GATEWAY") or "").strip() or None
        detail_type = (payment_detail_type or os.getenv("PAYSHARK_PAYMENT_DETAIL_TYPE") or "card").strip()

        data: Dict[str, Any] = {
            "merchant_id": self.merchant_id,
            "external_id": str(external_id),
            "amount": int(amount),
            "payment_detail_type": detail_type,
        }

        if gateway:
            data["payment_gateway"] = gateway
        else:
            # currency отправляем только когда НЕ задан payment_gateway
            if currency is not None:
                cur = str(currency).strip()
                if cur:
                    data["currency"] = cur

        if description:
            data["description"] = str(description)

        body_mode = (os.getenv("PAYSHARK_H2H_BODY") or "form").strip().lower()


        async with httpx.AsyncClient(timeout=self._timeout) as client:
            if body_mode == "json":
                r = await client.post(url, headers=self._headers(), json=data)
            else:
                # как в примере curl: -d ... (application/x-www-form-urlencoded)
                r = await client.post(url, headers=self._headers(), data=data)

        try:
            payload = r.json()
        except Exception:
            payload = {"raw_text": r.text}

        if r.status_code >= 400:
            raise RuntimeError(f"Payshark H2H HTTP {r.status_code}: {r.text[:1200]}")

        # Важно: Payshark может вернуть HTTP 200, но success=false / errors=... —
        # тогда сделка НЕ создана, и нужно показать понятную причину.
        if isinstance(payload, dict):
            if payload.get("success") is False:
                msg = str(payload.get("message") or "Unknown error")
                errs = payload.get("errors")
                if errs:
                    msg = f"{msg} | errors={errs}"
                raise RuntimeError(f"Payshark H2H error: {msg}")

            # Иногда приходит формат {message: ..., errors: {...}} без поля success
            if "errors" in payload and "message" in payload and "data" not in payload:
                msg = str(payload.get("message") or "Validation error")
                errs = payload.get("errors")
                if errs:
                    msg = f"{msg} | errors={errs}"
                raise RuntimeError(f"Payshark H2H error: {msg}")

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
            currency=str(obj.get("currency") or (currency or "")),
            payment_detail=payment_detail,
            link_page_url=str(link) if link else None,
            external_id=str(obj.get("external_id") or external_id),
            client_id=(str(obj.get("client_id")) if obj.get("client_id") is not None else None),
            raw=obj,
        )
