from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field, model_validator

from chatkit.widgets import Button, Card, Markdown, Text, Title


GETNET_AUTH_URL = os.getenv(
    "GETNET_AUTH_URL",
    "https://api.pre.globalgetnet.com/authentication/oauth2/access_token",
)
GETNET_PAYMENT_INTENT_URL = os.getenv(
    "GETNET_PAYMENT_INTENT_URL",
    "https://api.pre.globalgetnet.com/dpy/web-checkout/v1/payment-intent",
)


class CheckoutFlow(str, Enum):
    PAYMENT = "payment"
    AI_AGENT = "ai_agent"
    CARD_VERIFICATION = "card_verification"


class BillingAddress(BaseModel):
    street: str
    number: str
    country: str
    postal_code: str
    district: str
    city: str
    state: str
    complement: str | None = None


class Customer(BaseModel):
    customer_id: str
    name: str
    first_name: str
    last_name: str
    email: str
    checked_email: bool = False
    document_type: str
    document_number: str
    phone_number: str
    billing_address: BillingAddress


class Product(BaseModel):
    product_type: str = "cash_carry"
    title: str
    value: int
    quantity: int = 1


class ShippingAddress(BaseModel):
    street: str
    number: str
    country: str
    postal_code: str
    district: str
    city: str
    state: str


class Shipping(BaseModel):
    first_name: str
    last_name: str
    name: str
    phone_number: str
    address: ShippingAddress


class Payment(BaseModel):
    currency: str
    amount: int


class CheckoutIntentRequest(BaseModel):
    flow: CheckoutFlow
    order_id: str
    country: str = "BR"
    checkout_type: str = "IFRAME"
    customer: Customer
    payment: Payment | None = None
    product: list[Product] | None = None
    shipping: Shipping | None = None
    configurations: dict[str, bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_flow_payload(self) -> "CheckoutIntentRequest":
        if self.flow == CheckoutFlow.PAYMENT:
            missing = []
            if self.payment is None:
                missing.append("payment")
            if not self.product:
                missing.append("product")
            if self.shipping is None:
                missing.append("shipping")
            if missing:
                raise ValueError(
                    "payment flow requires payment, product and shipping data"
                )
        return self

    def to_getnet_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "country": self.country,
            "checkout_type": self.checkout_type,
            "order_id": self.order_id,
            "customer": self.customer.model_dump(exclude_none=True),
        }

        if self.flow == CheckoutFlow.PAYMENT:
            payload["payment"] = self.payment.model_dump(exclude_none=True)
            payload["product"] = [
                product.model_dump(exclude_none=True) for product in self.product or []
            ]
            payload["shipping"] = self.shipping.model_dump(exclude_none=True)
        elif self.flow == CheckoutFlow.AI_AGENT:
            payload["configurations"] = {"ai_agent": True}
        elif self.flow == CheckoutFlow.CARD_VERIFICATION:
            payload["configurations"] = {"card_verification": True}

        if self.configurations:
            payload.setdefault("configurations", {}).update(self.configurations)

        return payload


class CheckoutIntentResponse(BaseModel):
    payment_intent_id: str
    trade_name: str | None = None
    redirect_url: str
    access_token: str | None = None
    flow: CheckoutFlow


def build_checkout_result_widget(result: CheckoutIntentResponse) -> Card:
    return Card(
        id=f"checkout-result-{result.payment_intent_id}",
        padding=16,
        size="full",
        status={"text": "Checkout criado", "icon": "check-circle"},
        children=[
            Title(value="Checkout iniciado", size="lg"),
            Text(value=f"Flow: {result.flow.value}", size="sm", color="secondary"),
            Text(value=f"Payment intent: {result.payment_intent_id}", size="sm"),
            Markdown(
                value=(
                    f"[Abrir checkout agora]({result.redirect_url})\n\n"
                    "Se o link nao abrir automaticamente no ambiente atual, "
                    "clique na URL que uma nova aba se abrirá."
                )
            ),
        ],
    )


def build_checkout_error_widget(error_message: str) -> Card:
    return Card(
        id=f"checkout-error-{uuid4().hex[:8]}",
        padding=16,
        size="full",
        status={"text": "Falha ao iniciar checkout", "icon": "warning"},
        children=[
            Title(value="Nao foi possivel criar o checkout", size="lg"),
            Text(value=error_message, size="sm", color="danger"),
            Markdown(
                value=(
                    "Verifique as credenciais `GETNET_CLIENT_ID` e "
                    "`GETNET_CLIENT_SECRET` no backend/.env."
                )
            ),
        ],
    )


def build_demo_request(flow: CheckoutFlow) -> CheckoutIntentRequest:
    customer = Customer(
        customer_id="12345678912",
        name="Ana Silva Costa",
        first_name="Ana",
        last_name="Silva Costa",
        email="ana.silva@example.com.br",
        checked_email=False,
        document_type="CPF",
        document_number="12345678912",
        phone_number="5511987654321",
        billing_address=BillingAddress(
            street="Rua Augusta",
            number="2690",
            complement="Apto 82",
            district="Jardim Paulista",
            city="São Paulo",
            state="SP",
            country="BR",
            postal_code="01412100",
        ),
    )

    if flow == CheckoutFlow.PAYMENT:
        return CheckoutIntentRequest(
            flow=flow,
            order_id=f"ORDER_{uuid4().hex[:12].upper()}",
            customer=customer,
            payment=Payment(currency="BRL", amount=10000),
            product=[Product(title="Plano Starter", value=10000, quantity=1)],
            shipping=Shipping(
                first_name="Ana",
                last_name="Silva Costa",
                name="Ana Silva Costa",
                phone_number="5511987654321",
                address=ShippingAddress(
                    street="Rua Augusta",
                    number="2690",
                    country="BR",
                    postal_code="01412100",
                    district="Jardim Paulista",
                    city="São Paulo",
                    state="SP",
                ),
            ),
        )

    return CheckoutIntentRequest(
        flow=flow,
        order_id=f"ORDER_{uuid4().hex[:12].upper()}",
        customer=customer,
    )


def build_checkout_widget() -> Card:
    payment_request = build_demo_request(CheckoutFlow.PAYMENT)
    ai_agent_request = build_demo_request(CheckoutFlow.AI_AGENT)
    verification_request = build_demo_request(CheckoutFlow.CARD_VERIFICATION)

    return Card(
        id="checkout-root",
        padding=16,
        size="full",
        status={"text": "Checkout alternatives", "icon": "sparkle"},
        children=[
            Title(value="Iniciar checkout na conversa", size="lg"),
            Markdown(
                value=(
                    "Escolha o fluxo para testar no chat. "
                    "O checkout será aberto sem sair da conversa."
                )
            ),
            Text(
                value=(
                    "Pagamento padrão usa amount e produtos. "
                    "Tokenização e verificação usam iframe direto."
                ),
                size="sm",
                color="secondary",
            ),
            Button(
                label="Checkout padrão",
                style="primary",
                block=True,
                onClickAction={
                    "type": "checkout.launch",
                    "payload": {
                        "checkoutRequest": payment_request.model_dump(
                            exclude_none=True
                        ),
                    },
                },
            ),
            Button(
                label="Tokenizar cartão",
                variant="outline",
                block=True,
                onClickAction={
                    "type": "checkout.launch",
                    "payload": {
                        "checkoutRequest": ai_agent_request.model_dump(
                            exclude_none=True
                        ),
                    },
                },
            ),
            Button(
                label="Verificar cartão",
                variant="outline",
                block=True,
                onClickAction={
                    "type": "checkout.launch",
                    "payload": {
                        "checkoutRequest": verification_request.model_dump(
                            exclude_none=True
                        ),
                    },
                },
            ),
        ],
    )


@dataclass(slots=True)
class GetnetClient:
    client_id: str
    client_secret: str
    auth_url: str = GETNET_AUTH_URL
    payment_intent_url: str = GETNET_PAYMENT_INTENT_URL

    @classmethod
    def from_env(cls) -> "GetnetClient":
        client_id = os.getenv("GETNET_CLIENT_ID") or _read_env_file_value(
            "GETNET_CLIENT_ID"
        )
        client_secret = os.getenv("GETNET_CLIENT_SECRET") or _read_env_file_value(
            "GETNET_CLIENT_SECRET"
        )
        if not client_id or not client_secret:
            raise RuntimeError(
                "GETNET_CLIENT_ID and GETNET_CLIENT_SECRET must be set to create checkout intents"
            )
        return cls(client_id=client_id, client_secret=client_secret)

    async def create_payment_intent(
        self, request: CheckoutIntentRequest
    ) -> CheckoutIntentResponse:
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await self._get_access_token(client)
            response = await client.post(
                self.payment_intent_url,
                headers={"Authorization": f"Bearer {token}"},
                json=request.to_getnet_payload(),
            )
            response.raise_for_status()
            data = response.json()

        payment_intent_id = data.get("payment_intent_id")
        redirect_url = data.get("redirect_url")
        if not payment_intent_id or not redirect_url:
            raise RuntimeError(
                f"Getnet payment-intent response missing required fields: {data}"
            )

        return CheckoutIntentResponse(
            payment_intent_id=payment_intent_id,
            trade_name=data.get("trade_name"),
            redirect_url=redirect_url,
            access_token=data.get("access_token"),
            flow=request.flow,
        )

    async def _get_access_token(self, client: httpx.AsyncClient) -> str:
        response = await client.post(
            self.auth_url,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        data = response.json()
        if response.status_code >= 400:
            raise RuntimeError(
                f"Getnet auth failed ({response.status_code}): {data}"
            )

        token = data.get("access_token")
        if not token:
            raise RuntimeError(
                f"Getnet auth response missing access_token: {data}"
            )
        return token


def is_checkout_request(text: str | None) -> bool:
    if not text:
        return False
    normalized = text.casefold()
    return any(
        keyword in normalized
        for keyword in ("checkout", "pagar", "pagamento", "tokenizar", "verificar")
    )


def _read_env_file_value(key: str) -> str | None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return None

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        parsed_key, parsed_value = line.split("=", 1)
        if parsed_key.strip() != key:
            continue
        value = parsed_value.strip().strip('"').strip("'")
        return value or None

    return None