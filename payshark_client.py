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
    """external_id должен быть уникальным. Кодируем chat_id+plan для удобного трекинга."""
    return f"tg-{chat_id}-{plan}-{uuid.uuid4().hex}"


def _sanitize_base_url(raw: str) -> str:
    s = (raw or "").strip()
    # Частая ошибка: в переменной окружения сохраняют значение в кавычках.
    if (len(s) >= 2) and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
        s = s[1:-1].strip()
    s = s.rstrip("/")
    if s and not s.startswith(("http://", "https://")):
        s = "https://" + s
    return s


class PaysharkClient:
    """Мини‑клиент под Payshark H2H.

    Важно:
    - Для H2H /api/h2h/order используется заголовок Access-Token.
    - Тело — form-data/x-www-form-urlencoded (как в curl примере).
    - Для режима "любой банк" НЕ отправляем payment_gateway, а отправляем currency=rub.
    """

    def __init__(self):
        self.base_url = _sanitize_base_url(os.getenv("PAYSHARK_BASE_URL") or "https://app.payshark.io")

        self.api_key = (os.getenv("PAYSHARK_API_KEY") or os.getenv("PAYSHARK_ACCESS_TOKEN") or os.getenv("PAYSHARK_TOKEN") or "").strip()
        if (len(self.api_key) >= 2) and ((self.api_key[0] == '"' and self.api_key[-1] == '"') or (self.api_key[0] == "'" and self.api_key[-1] == "'")):
            self.api_key = self.api_key[1:-1].strip()

        self.merchant_id = (os.getenv("PAYSHARK_MERCHANT_ID") or "").strip()
        if (len(self.merchant_id) >= 2) and ((self.merchant_id[0] == '"' and self.merchant_id[-1] == '"') or (self.merchant_id[0] == "'" and self.merchant_id[-1] == "'")):
            self.merchant_id = self.merchant_id[1:-1].strip()

        self.timeout = float(os.getenv("PAYSHARK_TIMEOUT", "30"))

        if not self.api_key:
            raise RuntimeError("PAYSHARK_API_KEY is not set")
        if not self.merchant_id:
            raise RuntimeError("PAYSHARK_MERCHANT_ID is not set")

    def _headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "Access-Token": self.api_key,
        }

    async def create_h2h_order(
        self,
        *,
        amount: int,
        external_id: str,
        payment_detail_type: Optional[str] = None,
        payment_gateway: Optional[str] = None,
        currency: Optional[str] = None,
        description: Optional[str] = None,
    ) -> PaysharkOrder:
        url = f"{self.base_url}/api/h2h/order"

        mode = (os.getenv("PAYSHARK_H2H_MODE") or "anybank").strip().lower()  # anybank | gateway
        detail_type = (payment_detail_type or os.getenv("PAYSHARK_PAYMENT_DETAIL_TYPE") or "card").strip().lower()
        gateway_default = (os.getenv("PAYSHARK_PAYMENT_GATEWAY") or "sberbank").strip()
        currency_default = (os.getenv("PAYSHARK_CURRENCY") or "rub").strip().lower()

        data: Dict[str, str] = {
            "merchant_id": self.merchant_id,
            "external_id": str(external_id),
            "amount": str(int(amount)),
            "payment_detail_type": detail_type,
        }
        if description:
            data["description"] = str(description)

        if mode == "anybank":
            # В режиме "любой банк" payment_gateway НЕ передаём.
            data["currency"] = (currency or currency_default or "rub").strip().lower()
        else:
            gw = (payment_gateway or gateway_default).strip() if (payment_gateway or gateway_default) else ""
            if gw:
                data["payment_gateway"] = gw
            if currency:
                data["currency"] = str(currency).strip().lower()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(url, headers=self._headers(), data=data)

        if r.status_code >= 400:
            raise RuntimeError(f"Payshark H2H HTTP {r.status_code}: {r.text[:1200]}")

        payload: Dict[str, Any] = r.json() if r.content else {}
        if not payload.get("success", False):
            message = payload.get("message") or "Unknown error"
            raise RuntimeError(f"Payshark H2H error: {message}")

        d = payload.get("data") or {}
        order_id = str(d.get("id") or d.get("order_id") or "")
        status = str(d.get("status") or "created")
        amount_s = str(d.get("amount") or amount)
        currency_s = str(d.get("currency") or data.get("currency") or "rub")

        payment_detail = d.get("payment_detail")
        if payment_detail is None:
            payment_detail = d.get("payment_detail_data") or d.get("requisites") or d.get("details")

        link_page_url = d.get("link_page_url") or d.get("payment_url") or d.get("link")

        return PaysharkOrder(
            order_id=order_id,
            status=status,
            amount=amount_s,
            currency=currency_s,
            payment_detail=payment_detail,
            link_page_url=link_page_url,
            external_id=str(d.get("external_id") or external_id),
            raw=payload,
        )
