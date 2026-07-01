from __future__ import annotations

import logging
import os
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger("uvicorn.error")


def _mask_token(token: str) -> str:
    if len(token) <= 12:
        return "*" * len(token)
    return f"{token[:8]}...{token[-4:]}"

from chatkit.widgets import Button, Card, Col, Form, Input, Label, Markdown, Text, Title


GETNET_AUTH_URL = os.getenv(
    "GETNET_AUTH_URL",
    "https://api.pre.globalgetnet.com/authentication/oauth2/access_token",
)
GETNET_PAYMENT_INTENT_URL = os.getenv(
    "GETNET_PAYMENT_INTENT_URL",
    "https://api.pre.globalgetnet.com/dpy/web-checkout/v1/payment-intent",
)
GETNET_WALLET_API_BASE_URL = os.getenv(
    "GETNET_WALLET_API_BASE_URL",
    "https://api.pre.globalgetnet.com/ai-toolkit/v1",
)
GETNET_WALLET_CARDS_URL = os.getenv(
    "GETNET_WALLET_CARDS_URL",
    f"{GETNET_WALLET_API_BASE_URL}/cards",
)
GETNET_SEP_API_BASE_URL = os.getenv(
    "GETNET_SEP_API_BASE_URL",
    "https://api.pre.globalgetnet.com/dpm/cofre-gw-proxy/v1",
)
GETNET_SEP_TOKENIZE_URL = os.getenv(
    "GETNET_SEP_TOKENIZE_URL",
    f"{GETNET_SEP_API_BASE_URL}/tokens/card",
)
GETNET_SEP_CARDS_URL = os.getenv(
    "GETNET_SEP_CARDS_URL",
    f"{GETNET_SEP_API_BASE_URL}/cards",
)
GETNET_PAYMENTS_URL = os.getenv(
    "GETNET_PAYMENTS_URL",
    "https://api.pre.globalgetnet.com/dpm/payments-gwproxy/v2/payments",
)

# Fallback cards shown in Journey 3 when the wallet listing is unavailable.
MOCK_JOURNEY3_CARDS: list[dict[str, Any]] = [
    {
        "card_id": "mock_card_visa_4242",
        "brand": "Visa",
        "last_four_digits": "4242",
        "cardholder_name": "Ana Silva Costa",
    },
    {
        "card_id": "mock_card_master_5100",
        "brand": "Mastercard",
        "last_four_digits": "5100",
        "cardholder_name": "Ana Silva Costa",
    },
]


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


_SEP_BRAND_ALIASES = {
    "visa": "Visa",
    "mastercard": "Mastercard",
    "amex": "Amex",
    "american express": "Amex",
    "elo": "Elo",
    "hipercard": "Hipercard",
    "discover": "Discover",
}


class WalletCardCreateRequest(BaseModel):
    card_number: str
    customer_id: str
    brand: str
    cardholder_name: str
    expiration_month: str
    expiration_year: str
    cardholder_identification: str = "12345678912"
    verify_card: bool = False
    security_code: str | None = None

    @field_validator("brand")
    @classmethod
    def _normalize_brand(cls, value: str) -> str:
        normalized = value.strip()
        return _SEP_BRAND_ALIASES.get(normalized.casefold(), normalized)

    @field_validator("expiration_year")
    @classmethod
    def _normalize_expiration_year(cls, value: str) -> str:
        digits = value.strip()
        # Getnet vault expects a two-digit year (e.g. "30" for 2030).
        if len(digits) == 4 and digits.isdigit():
            return digits[-2:]
        return digits

    @field_validator("expiration_month")
    @classmethod
    def _normalize_expiration_month(cls, value: str) -> str:
        digits = value.strip()
        if digits.isdigit():
            return digits.zfill(2)
        return digits


def normalize_flow(value: str | CheckoutFlow | None) -> CheckoutFlow:
    if isinstance(value, CheckoutFlow):
        return value
    if isinstance(value, str):
        return CheckoutFlow(value)
    return CheckoutFlow.PAYMENT


def build_checkout_flow_selector_widget() -> Card:
    return Card(
        id="checkout-flow-selector",
        padding=16,
        size="full",
        background={"light": "surface-elevated", "dark": "surface-elevated"},
        status={"text": "Experiencia guiada", "icon": "sparkle"},
        children=[
            Title(value="Escolha a jornada de checkout", size="lg"),
            Markdown(
                value=(
                    "Uma coleta mais leve, clara e assistida. "
                    "Os dados entram em etapas e o iframe so aparece no momento final."
                )
            ),
            Text(
                value="Selecione a alternativa que melhor combina com a necessidade do cliente.",
                size="sm",
                color="secondary",
            ),
            Button(
                label="Pagamento padrao",
                color="info",
                variant="solid",
                pill=True,
                block=True,
                onClickAction={
                    "type": "checkout.flow.start",
                    "payload": {"flow": CheckoutFlow.PAYMENT.value},
                },
            ),
            Button(
                label="Tokenizar cartao",
                color="info",
                variant="outline",
                pill=True,
                block=True,
                onClickAction={
                    "type": "checkout.flow.start",
                    "payload": {"flow": CheckoutFlow.AI_AGENT.value},
                },
            ),
            Button(
                label="Verificar cartao",
                color="info",
                variant="outline",
                pill=True,
                block=True,
                onClickAction={
                    "type": "checkout.flow.start",
                    "payload": {"flow": CheckoutFlow.CARD_VERIFICATION.value},
                },
            ),
        ],
    )


def build_customer_form_widget(
    flow: CheckoutFlow,
    defaults: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> Card:
    values = defaults or {}
    customer_name = str(values.get("customer_name", ""))
    email = str(values.get("email", ""))
    document_number = str(values.get("document_number", ""))
    phone_number = str(values.get("phone_number", ""))
    street = str(values.get("street", ""))
    number = str(values.get("number", ""))
    district = str(values.get("district", "Centro"))
    city = str(values.get("city", ""))
    state = str(values.get("state", ""))
    postal_code = str(values.get("postal_code", ""))
    country = str(values.get("country", "BR"))

    children: list[Any] = [
        Title(value="Etapa 1: Dados do cliente", size="lg"),
        Text(value=f"Fluxo selecionado: {flow.value}", size="sm", color="secondary"),
    ]

    if error_message:
        children.append(Text(value=error_message, size="sm", color="danger"))

    children.append(
        Form(
            direction="col",
            gap=4,
            onSubmitAction={
                "type": "checkout.flow.customer.submit",
                "payload": {"flow": flow.value},
            },
            children=[
                Col(
                    gap=2,
                    children=[
                        Label(value="Nome completo", fieldName="customer_name"),
                        Input(
                            name="customer_name",
                            required=True,
                            defaultValue=customer_name,
                            placeholder="Ex.: Ana Silva Costa",
                        ),
                    ],
                ),
                Col(
                    gap=2,
                    children=[
                        Label(value="Email", fieldName="email"),
                        Input(
                            name="email",
                            inputType="email",
                            required=True,
                            defaultValue=email,
                            placeholder="nome@empresa.com",
                        ),
                    ],
                ),
                Col(
                    gap=2,
                    children=[
                        Label(value="Documento (CPF/CNPJ)", fieldName="document_number"),
                        Input(
                            name="document_number",
                            required=True,
                            defaultValue=document_number,
                            pattern=r"^[0-9\.\-/]{11,18}$",
                            placeholder="Somente numeros ou formatado",
                        ),
                    ],
                ),
                Col(
                    gap=2,
                    children=[
                        Label(value="Telefone", fieldName="phone_number"),
                        Input(
                            name="phone_number",
                            required=True,
                            defaultValue=phone_number,
                            pattern=r"^\+?[0-9\s\-\(\)]{10,20}$",
                            placeholder="Ex.: +55 11 98765-4321",
                        ),
                    ],
                ),
                Col(
                    gap=2,
                    children=[
                        Label(value="Rua", fieldName="street"),
                        Input(
                            name="street",
                            required=True,
                            defaultValue=street,
                            placeholder="Ex.: Rua Augusta",
                        ),
                    ],
                ),
                Col(
                    gap=2,
                    children=[
                        Label(value="Numero", fieldName="number"),
                        Input(
                            name="number",
                            required=True,
                            defaultValue=number,
                            pattern=r"^[0-9A-Za-z\-]{1,10}$",
                            placeholder="Ex.: 2690",
                        ),
                    ],
                ),
                Col(
                    gap=2,
                    children=[
                        Label(value="Bairro", fieldName="district"),
                        Input(name="district", required=True, defaultValue=district),
                    ],
                ),
                Col(
                    gap=2,
                    children=[
                        Label(value="Cidade", fieldName="city"),
                        Input(name="city", required=True, defaultValue=city),
                    ],
                ),
                Col(
                    gap=2,
                    children=[
                        Label(value="Estado", fieldName="state"),
                        Input(
                            name="state",
                            required=True,
                            defaultValue=state,
                            pattern=r"^[A-Za-z]{2}$",
                            placeholder="UF, ex.: SP",
                        ),
                    ],
                ),
                Col(
                    gap=2,
                    children=[
                        Label(value="CEP", fieldName="postal_code"),
                        Input(
                            name="postal_code",
                            required=True,
                            defaultValue=postal_code,
                            pattern=r"^[0-9\-]{8,10}$",
                            placeholder="Ex.: 01412-100",
                        ),
                    ],
                ),
                Col(
                    gap=2,
                    children=[
                        Label(value="Pais", fieldName="country"),
                        Input(
                            name="country",
                            required=True,
                            defaultValue=country,
                            pattern=r"^[A-Za-z]{2}$",
                            placeholder="Codigo ISO2, ex.: BR",
                        ),
                    ],
                ),
                Button(
                    label="Continuar",
                    color="info",
                    variant="solid",
                    pill=True,
                    block=True,
                    submit=True,
                ),
            ],
        )
    )

    children.append(
        Button(
            label="Trocar jornada",
            color="info",
            variant="ghost",
            pill=True,
            onClickAction={"type": "checkout.flow.restart", "payload": {}},
        )
    )

    return Card(
        id=f"checkout-customer-form-{flow.value}-{uuid4().hex[:8]}",
        padding=16,
        size="full",
        background={"light": "surface-elevated", "dark": "surface-elevated"},
        status={"text": "Formulario conversacional", "icon": "sparkle"},
        children=children,
    )


def build_payment_form_widget(
    flow: CheckoutFlow,
    defaults: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> Card:
    values = defaults or {}
    amount = str(values.get("amount", "10000"))
    currency = str(values.get("currency", "BRL"))
    product_title = str(values.get("product_title", "Plano Starter"))
    quantity = str(values.get("quantity", "1"))

    children: list[Any] = [
        Title(value="Etapa 2: Dados de pagamento", size="lg"),
        Text(
            value="Informe valor em centavos, produto e quantidade.",
            size="sm",
            color="secondary",
        ),
    ]

    if error_message:
        children.append(Text(value=error_message, size="sm", color="danger"))

    children.append(
        Form(
            direction="col",
            gap=4,
            onSubmitAction={
                "type": "checkout.flow.payment.submit",
                "payload": {"flow": flow.value},
            },
            children=[
                Col(
                    gap=2,
                    children=[
                        Label(value="Moeda", fieldName="currency"),
                        Input(
                            name="currency",
                            required=True,
                            defaultValue=currency,
                            pattern=r"^[A-Za-z]{3}$",
                            placeholder="ISO 4217, ex.: BRL",
                        ),
                    ],
                ),
                Col(
                    gap=2,
                    children=[
                        Label(value="Valor em centavos", fieldName="amount"),
                        Input(
                            name="amount",
                            inputType="number",
                            required=True,
                            defaultValue=amount,
                            pattern=r"^[0-9]{1,12}$",
                            placeholder="Ex.: 10000",
                        ),
                    ],
                ),
                Col(
                    gap=2,
                    children=[
                        Label(value="Titulo do produto", fieldName="product_title"),
                        Input(
                            name="product_title",
                            required=True,
                            defaultValue=product_title,
                            placeholder="Ex.: Plano Starter",
                        ),
                    ],
                ),
                Col(
                    gap=2,
                    children=[
                        Label(value="Quantidade", fieldName="quantity"),
                        Input(
                            name="quantity",
                            inputType="number",
                            required=True,
                            defaultValue=quantity,
                            pattern=r"^[0-9]{1,5}$",
                            placeholder="Ex.: 1",
                        ),
                    ],
                ),
                Button(
                    label="Revisar checkout",
                    color="info",
                    variant="solid",
                    pill=True,
                    block=True,
                    submit=True,
                ),
            ],
        )
    )

    children.append(
        Button(
            label="Voltar para dados do cliente",
            color="info",
            variant="ghost",
            pill=True,
            onClickAction={
                "type": "checkout.flow.back",
                "payload": {"flow": flow.value, "target": "customer"},
            },
        )
    )

    return Card(
        id=f"checkout-payment-form-{flow.value}-{uuid4().hex[:8]}",
        padding=16,
        size="full",
        background={"light": "surface-elevated", "dark": "surface-elevated"},
        status={"text": "Formulario conversacional", "icon": "sparkle"},
        children=children,
    )


def build_checkout_review_widget(request: CheckoutIntentRequest) -> Card:
    payload = request.to_getnet_payload()
    pretty_payload = str(payload).replace("{", "{\n").replace(",", ",\n")

    return Card(
        id=f"checkout-review-{request.flow.value}-{uuid4().hex[:8]}",
        padding=16,
        size="full",
        background={"light": "surface-elevated", "dark": "surface-elevated"},
        status={"text": "Revisao final", "icon": "sparkle"},
        children=[
            Title(value="Etapa final: confirmar checkout", size="lg"),
            Text(
                value=(
                    "Confira os dados abaixo com calma. Quando estiver tudo certo, "
                    "a etapa final abre o checkout hospedado."
                ),
                size="sm",
                color="secondary",
            ),
            Markdown(value=f"```text\n{pretty_payload}\n```"),
            Button(
                label="Confirmar e gerar checkout",
                color="info",
                variant="solid",
                pill=True,
                block=True,
                onClickAction={
                    "type": "checkout.flow.confirm",
                    "payload": {"flow": request.flow.value},
                },
            ),
            Button(
                label="Reiniciar jornada",
                color="info",
                variant="ghost",
                pill=True,
                block=True,
                onClickAction={"type": "checkout.flow.restart", "payload": {}},
            ),
        ],
    )


def build_iframe_feedback_widget(status: str, payment_intent_id: str) -> Card:
    if status == "completed":
        title = "Pagamento sinalizado como concluido"
        status_color = "success"
        subtitle = "A conversa pode continuar com proximos passos do pedido."
    elif status == "cancelled":
        title = "Checkout cancelado pelo usuario"
        status_color = "warning"
        subtitle = "Voce pode retomar a jornada e tentar novamente."
    else:
        title = "Checkout marcado como pendente"
        status_color = "secondary"
        subtitle = "Confirme no extrato e finalize quando estiver pronto."

    return Card(
        id=f"checkout-feedback-{payment_intent_id}-{uuid4().hex[:8]}",
        padding=16,
        size="full",
        background={"light": "surface-elevated", "dark": "surface-elevated"},
        status={"text": "Retorno do iframe", "icon": "sparkle"},
        children=[
            Title(value=title, size="lg"),
            Text(value=f"Payment intent: {payment_intent_id}", size="sm"),
            Text(value=subtitle, size="sm", color=status_color),
            Button(
                label="Iniciar nova jornada",
                color="info",
                variant="outline",
                pill=True,
                block=True,
                onClickAction={"type": "checkout.flow.restart", "payload": {}},
            ),
        ],
    )


def normalize_wallet_card_rows(payload: Any) -> list[dict[str, Any]]:
    """Normalize a wallet listing payload into a compact list of cards."""

    rows: list[Any] = []
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        for key in ("cards", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                rows = value
                break

    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue

        raw_last4 = (
            row.get("last_four_digits")
            or row.get("last4")
            or row.get("last_digits")
            or ""
        )
        last4 = str(raw_last4)[-4:] if raw_last4 else "----"

        holder = row.get("cardholder_name")
        if not holder and isinstance(row.get("cardholder"), dict):
            holder = row["cardholder"].get("name")

        result.append(
            {
                "card_id": str(row.get("card_id") or row.get("id") or ""),
                "brand": str(row.get("brand") or "Cartao"),
                "last4": last4,
                "cardholder_name": str(holder or ""),
            }
        )
    return result


def build_journey1_intro_widget() -> Card:
    return Card(
        id=f"journey1-intro-{uuid4().hex[:8]}",
        padding=16,
        size="full",
        background={"light": "surface-elevated", "dark": "surface-elevated"},
        status={"text": "Jornada 1: webcheckout Getnet", "icon": "sparkle"},
        children=[
            Title(value="Pagamento via webcheckout Getnet", size="lg"),
            Text(
                value=(
                    "Clique em Pagar para gerar a intencao de pagamento e receber o "
                    "link do webcheckout hospedado da Getnet."
                ),
                size="sm",
                color="secondary",
            ),
            Button(
                label="Pagar",
                color="info",
                variant="solid",
                pill=True,
                block=True,
                onClickAction={"type": "journey1.pay", "payload": {}},
            ),
        ],
    )


def build_journey3_intro_widget() -> Card:
    return Card(
        id=f"journey3-intro-{uuid4().hex[:8]}",
        padding=16,
        size="full",
        background={"light": "surface-elevated", "dark": "surface-elevated"},
        status={"text": "Jornada 3: formulario de cartao", "icon": "sparkle"},
        children=[
            Title(value="Pagamento com dados do cartao", size="lg"),
            Text(
                value=(
                    "Clique em Pagar para preencher os dados do cartao diretamente "
                    "no chat."
                ),
                size="sm",
                color="secondary",
            ),
            Button(
                label="Pagar",
                color="info",
                variant="solid",
                pill=True,
                block=True,
                onClickAction={"type": "journey3.cardform.start", "payload": {}},
            ),
        ],
    )


def build_card_payment_form_widget(
    defaults: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> Card:
    values = defaults or {}
    cardholder_name = str(values.get("cardholder_name", ""))
    customer_id = str(values.get("customer_id", ""))
    card_number = str(values.get("card_number", ""))
    expiration_month = str(values.get("expiration_month", ""))
    expiration_year = str(values.get("expiration_year", ""))
    security_code = str(values.get("security_code", ""))

    children: list[Any] = [
        Title(value="Dados do cartao", size="lg"),
        Text(
            value="Preencha os dados do cartao para o pagamento demonstrativo.",
            size="sm",
            color="secondary",
        ),
        Text(
            value="Valor: R$ 0,01 (somente demonstracao)",
            size="sm",
            color="secondary",
        ),
    ]

    if error_message:
        children.append(Text(value=error_message, size="sm", color="danger"))

    children.append(
        Form(
            direction="col",
            gap=4,
            onSubmitAction={"type": "journey3.cardform.submit", "payload": {}},
            children=[
                Col(
                    gap=2,
                    children=[
                        Label(value="Nome do titular", fieldName="cardholder_name"),
                        Input(
                            name="cardholder_name",
                            required=True,
                            defaultValue=cardholder_name,
                            placeholder="Ex.: Ana Silva Costa",
                        ),
                    ],
                ),
                Col(
                    gap=2,
                    children=[
                        Label(value="ID do cliente", fieldName="customer_id"),
                        Input(
                            name="customer_id",
                            required=True,
                            defaultValue=customer_id,
                            placeholder="Ex.: 12345678900",
                        ),
                    ],
                ),
                Col(
                    gap=2,
                    children=[
                        Label(value="Numero do cartao", fieldName="card_number"),
                        Input(
                            name="card_number",
                            required=True,
                            defaultValue=card_number,
                            pattern=r"^[0-9\s]{13,23}$",
                            placeholder="0000 0000 0000 0000",
                        ),
                    ],
                ),
                Col(
                    gap=2,
                    children=[
                        Label(value="Mes de expiracao", fieldName="expiration_month"),
                        Input(
                            name="expiration_month",
                            required=True,
                            defaultValue=expiration_month,
                            pattern=r"^[0-9]{1,2}$",
                            placeholder="MM",
                        ),
                    ],
                ),
                Col(
                    gap=2,
                    children=[
                        Label(value="Ano de expiracao", fieldName="expiration_year"),
                        Input(
                            name="expiration_year",
                            required=True,
                            defaultValue=expiration_year,
                            pattern=r"^[0-9]{2,4}$",
                            placeholder="AA ou AAAA",
                        ),
                    ],
                ),
                Col(
                    gap=2,
                    children=[
                        Label(value="CVV", fieldName="security_code"),
                        Input(
                            name="security_code",
                            required=True,
                            defaultValue=security_code,
                            pattern=r"^[0-9]{3,4}$",
                            placeholder="123",
                        ),
                    ],
                ),
                Button(
                    label="Pagar R$ 0,01",
                    color="info",
                    variant="solid",
                    pill=True,
                    block=True,
                    submit=True,
                ),
            ],
        )
    )

    return Card(
        id=f"journey3-cardform-{uuid4().hex[:8]}",
        padding=16,
        size="full",
        background={"light": "surface-elevated", "dark": "surface-elevated"},
        status={"text": "Jornada 3: formulario de cartao no chat", "icon": "sparkle"},
        children=children,
    )


def build_saved_card_selection_widget(
    cards: list[dict[str, Any]],
    source: str = "wallet",
) -> Card:
    children: list[Any] = [
        Title(value="Selecione um cartao para pagar", size="lg"),
        Text(
            value="Escolha um dos cartoes salvos para continuar com o pagamento.",
            size="sm",
            color="secondary",
        ),
    ]

    if source == "mock":
        children.append(
            Text(
                value="Exibindo cartoes de exemplo (carteira indisponivel no momento).",
                size="sm",
                color="warning",
            )
        )

    if not cards:
        children.append(
            Text(
                value="Nenhum cartao salvo encontrado. Cadastre um cartao para continuar.",
                size="sm",
                color="danger",
            )
        )

    for card in cards:
        last4 = str(card.get("last4") or "----")
        brand = str(card.get("brand") or "Cartao")
        holder = str(card.get("cardholder_name") or "")
        label = f"{brand} - final {last4}"
        if holder:
            label = f"{label} ({holder})"
        children.append(
            Button(
                label=label,
                color="info",
                variant="outline",
                pill=True,
                block=True,
                onClickAction={
                    "type": "savedcard.select",
                    "payload": {
                        "card_id": card.get("card_id", ""),
                        "last4": last4,
                        "brand": brand,
                        "cardholder_name": holder,
                    },
                },
            )
        )

    return Card(
        id=f"savedcard-selection-{uuid4().hex[:8]}",
        padding=16,
        size="full",
        background={"light": "surface-elevated", "dark": "surface-elevated"},
        status={"text": "Jornada 2: pagamento com cartao salvo", "icon": "sparkle"},
        children=children,
    )


def build_saved_card_order_widget(card: dict[str, Any]) -> Card:
    last4 = str(card.get("last4") or "----")
    brand = str(card.get("brand") or "Cartao")

    return Card(
        id=f"savedcard-order-{uuid4().hex[:8]}",
        padding=16,
        size="full",
        background={"light": "surface-elevated", "dark": "surface-elevated"},
        status={"text": "Revisao do pagamento", "icon": "sparkle"},
        children=[
            Title(value="Confirme o pagamento", size="lg"),
            Text(
                value="Revise o produto e o cartao selecionado antes de confirmar.",
                size="sm",
                color="secondary",
            ),
            Markdown(
                value=(
                    "**Produto:** Produto Demonstracao\n\n"
                    "**Valor:** R$ 0,01\n\n"
                    f"**Cartao:** {brand} - final {last4}"
                )
            ),
            Button(
                label="Pagar R$ 0,01",
                color="info",
                variant="solid",
                pill=True,
                block=True,
                onClickAction={"type": "savedcard.pay", "payload": {}},
            ),
            Button(
                label="Trocar cartao",
                color="info",
                variant="ghost",
                pill=True,
                block=True,
                onClickAction={"type": "savedcard.restart", "payload": {}},
            ),
        ],
    )


def build_payment_result_widget(
    success: bool,
    message: str,
    retry_action: str = "savedcard.restart",
    retry_label: str = "Escolher outro cartao",
) -> Card:
    if success:
        title = "Pagamento aprovado"
        status_color = "success"
        status_text = "Pagamento concluido"
    else:
        title = "Pagamento nao concluido"
        status_color = "danger"
        status_text = "Pagamento com falha"

    return Card(
        id=f"payment-result-{uuid4().hex[:8]}",
        padding=16,
        size="full",
        background={"light": "surface-elevated", "dark": "surface-elevated"},
        status={"text": status_text, "icon": "sparkle"},
        children=[
            Title(value=title, size="lg"),
            Text(value=message, size="sm", color=status_color),
            Button(
                label=retry_label,
                color="info",
                variant="outline",
                pill=True,
                block=True,
                onClickAction={"type": retry_action, "payload": {}},
            ),
        ],
    )


def build_request_from_journey_data(
    flow: CheckoutFlow,
    customer_data: dict[str, Any],
    payment_data: dict[str, Any] | None = None,
) -> CheckoutIntentRequest:
    payment_values = payment_data or {}

    full_name = _normalized_text(customer_data.get("customer_name"), "Cliente Checkout")
    first_name, last_name = split_name(full_name)
    country = _normalized_country(customer_data.get("country"))

    customer = Customer(
        customer_id=str(customer_data.get("customer_id") or _document_id(customer_data)),
        name=full_name,
        first_name=first_name,
        last_name=last_name,
        email=_normalized_text(customer_data.get("email"), "checkout@example.com"),
        checked_email=False,
        document_type=str(customer_data.get("document_type", "CPF")).upper(),
        document_number=_only_digits(customer_data.get("document_number"), "00000000000"),
        phone_number=_only_digits(customer_data.get("phone_number"), "5511999999999"),
        billing_address=BillingAddress(
            street=_normalized_text(customer_data.get("street"), "Rua Demo"),
            number=_normalized_text(customer_data.get("number"), "100"),
            country=country,
            postal_code=_only_digits(customer_data.get("postal_code"), "01001000"),
            district=_normalized_text(customer_data.get("district"), "Centro"),
            city=_normalized_text(customer_data.get("city"), "Sao Paulo"),
            state=_normalized_state(customer_data.get("state")),
            complement=str(customer_data.get("complement", "")) or None,
        ),
    )

    order_id = str(customer_data.get("order_id") or f"ORDER_{uuid4().hex[:12].upper()}")

    if flow == CheckoutFlow.PAYMENT:
        amount = int(str(payment_values.get("amount", "10000")))
        if amount <= 0:
            raise ValueError("amount deve ser maior que zero")

        quantity = int(str(payment_values.get("quantity", "1")))
        if quantity <= 0:
            raise ValueError("quantity deve ser maior que zero")

        currency = _normalized_currency(payment_values.get("currency"))
        product_title = _normalized_text(payment_values.get("product_title"), "Plano Starter")

        return CheckoutIntentRequest(
            flow=flow,
            order_id=order_id,
            country=country,
            customer=customer,
            payment=Payment(currency=currency, amount=amount),
            product=[Product(title=product_title, value=amount, quantity=quantity)],
            shipping=Shipping(
                first_name=first_name,
                last_name=last_name,
                name=full_name,
                phone_number=customer.phone_number,
                address=ShippingAddress(
                    street=customer.billing_address.street,
                    number=customer.billing_address.number,
                    country=customer.billing_address.country,
                    postal_code=customer.billing_address.postal_code,
                    district=customer.billing_address.district,
                    city=customer.billing_address.city,
                    state=customer.billing_address.state,
                ),
            ),
        )

    return CheckoutIntentRequest(
        flow=flow,
        order_id=order_id,
        country=country,
        customer=customer,
    )


def split_name(value: str) -> tuple[str, str]:
    parts = [item for item in value.split() if item]
    if not parts:
        return ("Cliente", "Checkout")
    if len(parts) == 1:
        return (parts[0], "Checkout")
    return (parts[0], " ".join(parts[1:]))


def _document_id(customer_data: dict[str, Any]) -> str:
    document = str(customer_data.get("document_number", "00000000000"))
    digits = "".join(ch for ch in document if ch.isdigit())
    return digits or "00000000000"


def _normalized_text(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    return text or fallback


def _only_digits(value: Any, fallback: str) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return digits or fallback


def _normalized_country(value: Any) -> str:
    code = _normalized_text(value, "BR").upper()
    if len(code) != 2 or not code.isalpha():
        raise ValueError("country deve ser um codigo ISO2, por exemplo BR")
    return code


def _normalized_state(value: Any) -> str:
    state = _normalized_text(value, "SP").upper()
    if len(state) != 2 or not state.isalpha():
        raise ValueError("state deve ter 2 letras, por exemplo SP")
    return state


def _normalized_currency(value: Any) -> str:
    currency = _normalized_text(value, "BRL").upper()
    if len(currency) != 3 or not currency.isalpha():
        raise ValueError("currency deve ter 3 letras, por exemplo BRL")
    return currency


def build_checkout_result_widget(result: CheckoutIntentResponse) -> Card:
    return Card(
        id=f"checkout-result-{result.payment_intent_id}",
        padding=16,
        size="full",
        background={"light": "surface-elevated", "dark": "surface-elevated"},
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
        background={"light": "surface-elevated", "dark": "surface-elevated"},
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


def build_demo_request(
    flow: CheckoutFlow, amount: int = 1
) -> CheckoutIntentRequest:
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
            payment=Payment(currency="BRL", amount=amount),
            product=[Product(title="Produto Demonstracao", value=amount, quantity=1)],
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
    return build_checkout_flow_selector_widget()


@dataclass(slots=True)
class GetnetClient:
    client_id: str
    client_secret: str
    auth_url: str = GETNET_AUTH_URL
    payment_intent_url: str = GETNET_PAYMENT_INTENT_URL

    @classmethod
    def from_env(cls) -> "GetnetClient":
        client_id = _read_first_available_env_value(
            ["GETNET_CLIENT_ID", "GETNET_CLIENT_ID_API"]
        )
        client_secret = _read_first_available_env_value(
            ["GETNET_CLIENT_SECRET", "GETNET_CLIENT_SECRET_API"]
        )
        if not client_id or not client_secret:
            raise RuntimeError(
                "GETNET_CLIENT_ID/GETNET_CLIENT_SECRET (or *_API variants) must be set to create checkout intents"
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


_SENSITIVE_CARD_FIELDS = ("number_token", "security_code", "card_number")


def _sanitize_wallet_cards(payload: Any) -> Any:
    """Remove sensitive fields (e.g. number_token) from wallet responses."""

    def _clean(card: Any) -> Any:
        if isinstance(card, dict):
            return {
                key: value
                for key, value in card.items()
                if key not in _SENSITIVE_CARD_FIELDS
            }
        return card

    if isinstance(payload, list):
        return [_clean(card) for card in payload]

    if isinstance(payload, dict):
        for container_key in ("cards", "items"):
            rows = payload.get(container_key)
            if isinstance(rows, list):
                sanitized = dict(payload)
                sanitized[container_key] = [_clean(card) for card in rows]
                return sanitized
        return _clean(payload)

    return payload


@dataclass(slots=True)
class GetnetWalletClient:
    client_id: str
    client_secret: str
    auth_url: str = GETNET_AUTH_URL
    cards_url: str = GETNET_SEP_CARDS_URL
    tokenize_url: str = GETNET_SEP_TOKENIZE_URL
    payments_url: str = GETNET_PAYMENTS_URL

    @classmethod
    def from_env(cls) -> "GetnetWalletClient":
        client_id = _read_first_available_env_value(["GETNET_CLIENT_ID_API"])
        client_secret = _read_first_available_env_value(["GETNET_CLIENT_SECRET_API"])

        if not client_id or not client_secret:
            raise RuntimeError(
                "GETNET_CLIENT_ID_API and GETNET_CLIENT_SECRET_API must be set to access wallet endpoints"
            )

        return cls(client_id=client_id, client_secret=client_secret)

    async def fetch_access_token(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            return await self._request_access_token(client)

    async def list_cards(
        self,
        customer_id: str,
        access_token: str | None = None,
    ) -> Any:
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = access_token or await self._get_access_token(client)
            response = await client.get(
                self.cards_url,
                headers={"Authorization": f"Bearer {token}"},
                params={"customer_id": customer_id},
            )
            # SEP returns 404 when the customer has no cards yet; treat it as
            # an empty wallet instead of surfacing an error to the caller.
            if response.status_code == 404:
                return []
            if response.status_code >= 400:
                raise RuntimeError(
                    "Getnet wallet list_cards failed "
                    f"({response.status_code}): {response.text}"
                )
            return _sanitize_wallet_cards(response.json())

    async def tokenize_card(
        self,
        card_number: str,
        access_token: str | None = None,
    ) -> str:
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = access_token or await self._get_access_token(client)
            response = await client.post(
                self.tokenize_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json;charset=utf-8",
                },
                json={"card_number": card_number},
            )
            if response.status_code >= 400:
                raise RuntimeError(
                    "Getnet SEP tokenize_card failed "
                    f"({response.status_code}): {response.text}"
                )
            data = response.json()
            number_token = data.get("number_token")
            if not number_token:
                raise RuntimeError(
                    f"Getnet SEP tokenize response missing number_token: {data}"
                )
            return str(number_token)

    async def create_card(
        self,
        payload: WalletCardCreateRequest,
        access_token: str | None = None,
    ) -> Any:
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = access_token or await self._get_access_token(client)

            number_token = await self.tokenize_card(
                payload.card_number, access_token=token
            )

            body = payload.model_dump(exclude_none=True)
            body.pop("card_number", None)
            body["number_token"] = number_token

            logger.info(
                "POST %s | Authorization: Bearer %s | body=%s",
                self.cards_url,
                _mask_token(token),
                {**body, "number_token": "***", "security_code": "***"},
            )
            response = await client.post(
                self.cards_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json; charset=utf-8",
                },
                json=body,
            )
            if response.status_code >= 400:
                raise RuntimeError(
                    "Getnet SEP create_card failed "
                    f"({response.status_code}): {response.text}"
                )
            return response.json()

    async def execute_payment(
        self,
        card_id: str,
        amount: int,
        currency: str,
        customer_id: str,
        order_id: str,
        access_token: str | None = None,
    ) -> Any:
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = access_token or await self._get_access_token(client)
            body = {
                "idempotency_key": str(uuid4()),
                "request_id": str(uuid4()),
                "order_id": order_id,
                "data": {
                    "amount": amount,
                    "currency": currency,
                    "customer_id": customer_id,
                    "payment": {
                        "payment_method": "CREDIT",
                        "transaction_type": "FULL",
                        "number_installments": 1,
                    },
                },
            }
            response = await client.post(
                f"{self.payments_url}/{card_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json=body,
            )
            if response.status_code >= 400:
                raise RuntimeError(
                    "Getnet execute_payment failed "
                    f"({response.status_code}): {response.text}"
                )
            return response.json()

    async def delete_card(
        self,
        card_id: str,
        access_token: str | None = None,
    ) -> None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = access_token or await self._get_access_token(client)
            response = await client.delete(
                f"{self.cards_url}/{card_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code >= 400:
                raise RuntimeError(
                    "Getnet wallet delete_card failed "
                    f"({response.status_code}): {response.text}"
                )

    async def _get_access_token(self, client: httpx.AsyncClient) -> str:
        data = await self._request_access_token(client)
        return str(data["access_token"])

    async def _request_access_token(self, client: httpx.AsyncClient) -> dict[str, Any]:
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
            raise RuntimeError(f"Getnet auth failed ({response.status_code}): {data}")

        token = data.get("access_token")
        if not token:
            raise RuntimeError(f"Getnet auth response missing access_token: {data}")
        return data


def is_checkout_request(text: str | None) -> bool:
    if not text:
        return False
    normalized = text.casefold()
    return any(
        keyword in normalized
        for keyword in ("checkout", "pagar", "pagamento", "tokenizar", "verificar")
    )


def _read_env_file_value(key: str) -> str | None:
    env_paths = [
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
        Path(__file__).resolve().parent.parent.parent / "frontend" / ".env",
    ]

    for env_path in env_paths:
        if not env_path.exists():
            continue

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


def _read_first_available_env_value(keys: list[str]) -> str | None:
    for key in keys:
        value = os.getenv(key) or _read_env_file_value(key)
        if value:
            return value
    return None