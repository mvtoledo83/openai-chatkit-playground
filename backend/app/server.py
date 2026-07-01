"""ChatKit server that streams responses from a single assistant."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

from chatkit.server import ChatKitServer, stream_widget

from agents import Runner
from chatkit.agents import AgentContext, simple_to_agent_input, stream_agent_response
from chatkit.types import Action, ThreadMetadata, ThreadStreamEvent, UserMessageItem, WidgetItem

from .checkout import (
    CheckoutIntentRequest,
    CheckoutFlow,
    GetnetClient,
    GetnetWalletClient,
    build_card_payment_form_widget,
    build_checkout_flow_selector_widget,
    build_checkout_error_widget,
    build_checkout_review_widget,
    build_checkout_result_widget,
    build_customer_form_widget,
    build_demo_request,
    build_iframe_feedback_widget,
    build_journey1_intro_widget,
    build_journey3_intro_widget,
    build_payment_form_widget,
    build_payment_result_widget,
    build_request_from_journey_data,
    build_saved_card_order_widget,
    build_saved_card_selection_widget,
    is_checkout_request,
    normalize_flow,
    normalize_wallet_card_rows,
    MOCK_JOURNEY3_CARDS,
)
from .memory_store import MemoryStore
from agents import Agent


MAX_RECENT_ITEMS = 30
MODEL = "gpt-4.1-mini"


def _ensure_openai_api_key() -> None:
    if os.getenv("OPENAI_API_KEY"):
        return

    candidate_paths = [
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
    ]

    for env_path in candidate_paths:
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() != "OPENAI_API_KEY":
                continue
            parsed = value.strip().strip('"').strip("'")
            if parsed:
                os.environ["OPENAI_API_KEY"] = parsed
                return


_ensure_openai_api_key()


assistant_agent = Agent[AgentContext[dict[str, Any]]](
    model=MODEL,
    name="Starter Assistant",
    instructions=(
        "You are a concise, helpful assistant. "
        "Keep replies short and focus on directly answering "
        "the user's request."
    ),
)


class StarterChatServer(ChatKitServer[dict[str, Any]]):
    """Server implementation that keeps conversation state in memory."""

    def __init__(self) -> None:
        self.store: MemoryStore = MemoryStore()
        super().__init__(self.store)

    async def respond(
        self,
        thread: ThreadMetadata,
        item: UserMessageItem | None,
        context: dict[str, Any],
    ) -> AsyncIterator[ThreadStreamEvent]:
        items_page = await self.store.load_thread_items(
            thread.id,
            after=None,
            limit=MAX_RECENT_ITEMS,
            order="desc",
            context=context,
        )
        items = list(reversed(items_page.data))

        checkout_source = item or _latest_user_message(items)
        if checkout_source is not None and _checkout_requested(checkout_source):
            active_journey = _resolve_active_journey(thread, context)
            _remember_active_journey(thread, active_journey or 1, context)
            if active_journey == 2:
                cards, source = await _load_saved_cards(thread)
                widget = build_saved_card_selection_widget(cards, source)
                copy_text = "Selecione um cartao salvo para pagar."
            elif active_journey == 3:
                widget = build_journey3_intro_widget()
                copy_text = "Clique em Pagar para preencher os dados do cartao."
            else:
                widget = build_journey1_intro_widget()
                copy_text = "Clique em Pagar para gerar o link do webcheckout."
            await self.store.save_thread(thread, context=context)
            async for event in stream_widget(
                thread,
                widget,
                copy_text=copy_text,
                generate_id=lambda item_type: self.store.generate_item_id(
                    item_type, thread, context
                ),
            ):
                yield event
            return

        agent_input = await simple_to_agent_input(items)

        agent_context = AgentContext(
            thread=thread,
            store=self.store,
            request_context=context,
        )

        result = Runner.run_streamed(
            assistant_agent,
            agent_input,
            context=agent_context,
        )

        async for event in stream_agent_response(agent_context, result):
            yield event

    async def action(
        self,
        thread: ThreadMetadata,
        action: Action[str, Any],
        sender: WidgetItem | None,
        context: dict[str, Any],
    ) -> AsyncIterator[ThreadStreamEvent]:
        _ = sender

        payload = action.payload if isinstance(action.payload, dict) else {}

        if action.type == "journey.select":
            journey_num = _coerce_journey(payload.get("journey"))
            thread.metadata["active_journey"] = journey_num
            thread.metadata.pop("checkout_journey", None)
            thread.metadata.pop("savedcard_selected_card", None)
            customer_id = str(
                payload.get("customerId") or payload.get("customer_id") or ""
            ).strip()
            if customer_id:
                thread.metadata["savedcard_customer_id"] = customer_id
            await self.store.save_thread(thread, context=context)

            if journey_num == 2:
                cards, source = await _load_saved_cards(thread)
                widget = build_saved_card_selection_widget(cards, source)
                copy_text = "Selecione um cartao salvo para pagar."
            elif journey_num == 3:
                widget = build_journey3_intro_widget()
                copy_text = "Clique em Pagar para preencher os dados do cartao."
            else:
                widget = build_journey1_intro_widget()
                copy_text = "Clique em Pagar para gerar o link do webcheckout."
            async for event in _stream_checkout_widget(
                self, thread, context, widget, copy_text
            ):
                yield event
            return

        if action.type == "journey1.pay":
            async for event in _handle_journey1_pay(self, thread, context):
                yield event
            return

        if action.type == "journey3.cardform.start":
            thread.metadata["active_journey"] = 3
            await self.store.save_thread(thread, context=context)
            widget = build_card_payment_form_widget(
                defaults={"customer_id": _default_saved_card_customer_id(thread)}
            )
            async for event in _stream_checkout_widget(
                self,
                thread,
                context,
                widget,
                "Preencha os dados do cartao para o pagamento demonstrativo.",
            ):
                yield event
            return

        if action.type == "journey3.cardform.submit":
            thread.metadata["active_journey"] = 3
            await self.store.save_thread(thread, context=context)
            form_values = _extract_form_values(payload)
            required = [
                "cardholder_name",
                "customer_id",
                "card_number",
                "expiration_month",
                "expiration_year",
                "security_code",
            ]
            missing = [key for key in required if not str(form_values.get(key, "")).strip()]
            if missing:
                widget = build_card_payment_form_widget(
                    defaults=form_values,
                    error_message="Preencha todos os campos obrigatorios do cartao.",
                )
                async for event in _stream_checkout_widget(
                    self,
                    thread,
                    context,
                    widget,
                    "Dados incompletos. Revise o formulario.",
                ):
                    yield event
                return

            brand = _detect_card_brand(str(form_values.get("card_number", "")))
            last4 = _last_four(str(form_values.get("card_number", "")))
            widget = build_payment_result_widget(
                True,
                (
                    f"Pagamento de R$ 0,01 concluido (demonstracao) com o cartao "
                    f"{brand} final {last4}."
                ),
                retry_action="journey3.cardform.start",
                retry_label="Novo pagamento",
            )
            async for event in _stream_checkout_widget(
                self, thread, context, widget, "Pagamento demonstrativo concluido."
            ):
                yield event
            return

        if action.type == "savedcard.select":
            card = {
                "card_id": str(payload.get("card_id", "")),
                "last4": str(payload.get("last4", "----")),
                "brand": str(payload.get("brand", "Cartao")),
                "cardholder_name": str(payload.get("cardholder_name", "")),
            }
            thread.metadata["savedcard_selected_card"] = card
            thread.metadata["active_journey"] = 2
            await self.store.save_thread(thread, context=context)
            widget = build_saved_card_order_widget(card)
            async for event in _stream_checkout_widget(
                self, thread, context, widget, "Revise o pagamento e confirme."
            ):
                yield event
            return

        if action.type == "savedcard.restart":
            thread.metadata.pop("savedcard_selected_card", None)
            thread.metadata["active_journey"] = 2
            await self.store.save_thread(thread, context=context)
            cards, source = await _load_saved_cards(thread)
            widget = build_saved_card_selection_widget(cards, source)
            async for event in _stream_checkout_widget(
                self, thread, context, widget, "Selecione um cartao salvo para pagar."
            ):
                yield event
            return

        if action.type == "savedcard.pay":
            async for event in _handle_saved_card_payment(self, thread, context):
                yield event
            return

        if action.type == "checkout.flow.start":
            flow = normalize_flow(payload.get("flow"))
            journey = {
                "flow": flow.value,
                "step": "customer",
                "customer_data": {},
                "payment_data": {},
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            thread.metadata["checkout_journey"] = journey
            await self.store.save_thread(thread, context=context)
            widget = build_customer_form_widget(flow)
            async for event in _stream_checkout_widget(
                self,
                thread,
                context,
                widget,
                "Etapa 1 iniciada: dados do cliente",
            ):
                yield event
            return

        if action.type == "checkout.flow.restart":
            thread.metadata.pop("checkout_journey", None)
            await self.store.save_thread(thread, context=context)
            widget = build_checkout_flow_selector_widget()
            async for event in _stream_checkout_widget(
                self,
                thread,
                context,
                widget,
                "Jornada reiniciada. Escolha uma nova alternativa.",
            ):
                yield event
            return

        if action.type == "checkout.flow.back":
            journey = _get_journey(thread)
            if not journey:
                widget = build_checkout_flow_selector_widget()
                async for event in _stream_checkout_widget(
                    self,
                    thread,
                    context,
                    widget,
                    "Nao havia jornada ativa. Escolha uma alternativa.",
                ):
                    yield event
                return

            flow = normalize_flow(journey.get("flow"))
            widget = build_customer_form_widget(
                flow,
                defaults=_as_dict(journey.get("customer_data")),
            )
            journey["step"] = "customer"
            journey["updated_at"] = datetime.now(timezone.utc).isoformat()
            thread.metadata["checkout_journey"] = journey
            await self.store.save_thread(thread, context=context)
            async for event in _stream_checkout_widget(
                self,
                thread,
                context,
                widget,
                "Voltamos para os dados do cliente.",
            ):
                yield event
            return

        if action.type == "checkout.flow.customer.submit":
            journey = _get_journey(thread)
            if not journey:
                widget = build_checkout_flow_selector_widget()
                async for event in _stream_checkout_widget(
                    self,
                    thread,
                    context,
                    widget,
                    "Jornada expirada. Escolha o fluxo novamente.",
                ):
                    yield event
                return

            flow = normalize_flow(journey.get("flow"))
            form_values = _extract_form_values(payload)
            journey["last_customer_payload"] = form_values
            try:
                customer_data = _parse_customer_values(form_values)
            except ValueError as exc:
                widget = build_customer_form_widget(
                    flow,
                    defaults=form_values,
                    error_message=str(exc),
                )
                async for event in _stream_checkout_widget(
                    self,
                    thread,
                    context,
                    widget,
                    "Revise os dados do cliente e tente novamente.",
                ):
                    yield event
                return

            journey["customer_data"] = customer_data
            journey["step"] = "payment" if flow == CheckoutFlow.PAYMENT else "review"
            journey["updated_at"] = datetime.now(timezone.utc).isoformat()
            thread.metadata["checkout_journey"] = journey
            await self.store.save_thread(thread, context=context)

            if flow == CheckoutFlow.PAYMENT:
                widget = build_payment_form_widget(
                    flow,
                    defaults=_as_dict(journey.get("payment_data")),
                )
                copy_text = "Etapa 2: preencha os dados de pagamento."
            else:
                checkout_request = build_request_from_journey_data(
                    flow,
                    customer_data,
                    _as_dict(journey.get("payment_data")),
                )
                journey["draft_checkout_request"] = checkout_request.model_dump(
                    exclude_none=True
                )
                thread.metadata["checkout_journey"] = journey
                await self.store.save_thread(thread, context=context)
                widget = build_checkout_review_widget(checkout_request)
                copy_text = "Dados do cliente prontos. Revise e confirme."

            async for event in _stream_checkout_widget(
                self,
                thread,
                context,
                widget,
                copy_text,
            ):
                yield event
            return

        if action.type == "checkout.flow.payment.submit":
            journey = _get_journey(thread)
            if not journey:
                widget = build_checkout_flow_selector_widget()
                async for event in _stream_checkout_widget(
                    self,
                    thread,
                    context,
                    widget,
                    "Jornada expirada. Escolha o fluxo novamente.",
                ):
                    yield event
                return

            flow = normalize_flow(journey.get("flow"))
            if flow != CheckoutFlow.PAYMENT:
                widget = build_customer_form_widget(flow)
                async for event in _stream_checkout_widget(
                    self,
                    thread,
                    context,
                    widget,
                    "Esse fluxo nao exige dados de pagamento.",
                ):
                    yield event
                return

            form_values = _extract_form_values(payload)
            journey["last_payment_payload"] = form_values
            journey["payment_data"] = form_values
            journey["step"] = "review"
            customer_data = _as_dict(journey.get("customer_data"))

            try:
                checkout_request = build_request_from_journey_data(
                    flow,
                    customer_data,
                    form_values,
                )
            except Exception as exc:
                widget = build_payment_form_widget(
                    flow,
                    defaults=form_values,
                    error_message=str(exc),
                )
                async for event in _stream_checkout_widget(
                    self,
                    thread,
                    context,
                    widget,
                    "Revise os dados de pagamento e tente novamente.",
                ):
                    yield event
                return

            journey["draft_checkout_request"] = checkout_request.model_dump(
                exclude_none=True
            )
            journey["updated_at"] = datetime.now(timezone.utc).isoformat()
            thread.metadata["checkout_journey"] = journey
            await self.store.save_thread(thread, context=context)
            widget = build_checkout_review_widget(checkout_request)
            async for event in _stream_checkout_widget(
                self,
                thread,
                context,
                widget,
                "Dados de pagamento recebidos. Revise e confirme.",
            ):
                yield event
            return

        if action.type in {"checkout.flow.confirm", "checkout.launch"}:
            async for event in _handle_checkout_launch(self, thread, payload, context):
                yield event
            return

        if action.type == "checkout.iframe.feedback":
            status = str(payload.get("status", "pending")).lower().strip() or "pending"
            latest_checkout = thread.metadata.get("latest_checkout")
            if not isinstance(latest_checkout, dict):
                widget = build_checkout_error_widget(
                    "Nao encontramos checkout ativo para registrar retorno."
                )
                async for event in _stream_checkout_widget(
                    self,
                    thread,
                    context,
                    widget,
                    "Sem checkout ativo para atualizar.",
                ):
                    yield event
                return

            payment_intent_id = str(latest_checkout.get("payment_intent_id", ""))
            latest_checkout["status"] = status
            latest_checkout["updated_at"] = datetime.now(timezone.utc).isoformat()
            thread.metadata["latest_checkout"] = latest_checkout
            await self.store.save_thread(thread, context=context)
            widget = build_iframe_feedback_widget(status, payment_intent_id)
            async for event in _stream_checkout_widget(
                self,
                thread,
                context,
                widget,
                f"Checkout {status} para {payment_intent_id}.",
            ):
                yield event
            return

        return


async def _handle_checkout_launch(
    server: StarterChatServer,
    thread: ThreadMetadata,
    payload: dict[str, Any],
    context: dict[str, Any],
) -> AsyncIterator[ThreadStreamEvent]:
    widget = None
    copy_text = "Falha ao iniciar checkout"
    try:
        checkout_payload = payload.get("checkoutRequest")
        if not isinstance(checkout_payload, dict):
            journey = _get_journey(thread)
            if journey:
                draft_payload = journey.get("draft_checkout_request")
                if isinstance(draft_payload, dict):
                    checkout_payload = draft_payload

        if not isinstance(checkout_payload, dict):
            raise ValueError("checkoutRequest ausente na action")

        checkout_request = CheckoutIntentRequest.model_validate(checkout_payload)
        client = GetnetClient.from_env()
        result = await client.create_payment_intent(checkout_request)
        widget = build_checkout_result_widget(result)
        copy_text = f"Checkout criado: {result.redirect_url}"
        checkout_mode = "external" if _get_active_journey(thread) == 2 else "iframe"
        thread.metadata["latest_checkout"] = {
            "payment_intent_id": result.payment_intent_id,
            "redirect_url": result.redirect_url,
            "flow": result.flow.value,
            "status": "created",
            "mode": checkout_mode,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        thread.metadata.pop("checkout_journey", None)
        await server.store.save_thread(thread, context=context)
    except Exception as exc:
        widget = build_checkout_error_widget(str(exc))

    async for event in _stream_checkout_widget(
        server,
        thread,
        context,
        widget,
        copy_text,
    ):
        yield event


async def _stream_checkout_widget(
    server: StarterChatServer,
    thread: ThreadMetadata,
    context: dict[str, Any],
    widget: Any,
    copy_text: str,
) -> AsyncIterator[ThreadStreamEvent]:
    async for event in stream_widget(
        thread,
        widget,
        copy_text=copy_text,
        generate_id=lambda item_type: server.store.generate_item_id(
            item_type, thread, context
        ),
    ):
        yield event


def _get_journey(thread: ThreadMetadata) -> dict[str, Any] | None:
    journey = thread.metadata.get("checkout_journey")
    if isinstance(journey, dict):
        return journey
    return None


def _coerce_journey(value: Any) -> int:
    try:
        journey = int(value)
    except (TypeError, ValueError):
        return 1
    return journey if journey in (1, 2, 3) else 1


def _get_active_journey(thread: ThreadMetadata) -> int | None:
    value = thread.metadata.get("active_journey")
    if isinstance(value, int) and value in (1, 2, 3):
        return value
    return None


def _resolve_active_journey(
    thread: ThreadMetadata, context: dict[str, Any]
) -> int | None:
    stored = _get_active_journey(thread)
    if stored is not None:
        return stored
    return _journey_from_context(context)


def _journey_from_context(context: dict[str, Any]) -> int | None:
    request = context.get("request") if isinstance(context, dict) else None
    headers = getattr(request, "headers", None)
    if headers is None:
        return None
    raw = headers.get("x-journey") or headers.get("X-Journey")
    if not raw:
        return None
    try:
        journey = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return journey if journey in (1, 2, 3) else None


def _remember_active_journey(
    thread: ThreadMetadata, journey: int, context: dict[str, Any]
) -> None:
    thread.metadata["active_journey"] = journey


def _default_saved_card_customer_id(thread: ThreadMetadata) -> str:
    stored = str(thread.metadata.get("savedcard_customer_id") or "").strip()
    if stored:
        return stored
    return (
        os.getenv("CARDS_CUSTOMER_ID")
        or os.getenv("GETNET_CUSTOMER_ID")
        or "12345678900"
    )


async def _load_saved_cards(
    thread: ThreadMetadata,
) -> tuple[list[dict[str, Any]], str]:
    customer_id = _default_saved_card_customer_id(thread)

    try:
        client = GetnetWalletClient.from_env()
        payload = await client.list_cards(customer_id)
        cards = [
            card
            for card in normalize_wallet_card_rows(payload)
            if card.get("card_id")
        ]
        if cards:
            return cards, "wallet"
    except Exception:
        pass

    return normalize_wallet_card_rows(MOCK_JOURNEY3_CARDS), "mock"


async def _handle_journey1_pay(
    server: "StarterChatServer",
    thread: ThreadMetadata,
    context: dict[str, Any],
) -> AsyncIterator[ThreadStreamEvent]:
    thread.metadata["active_journey"] = 1
    try:
        checkout_request = build_demo_request(CheckoutFlow.PAYMENT, amount=1)
        client = GetnetClient.from_env()
        result = await client.create_payment_intent(checkout_request)
        widget = build_checkout_result_widget(result)
        copy_text = f"Link do webcheckout gerado: {result.redirect_url}"
    except Exception as exc:
        widget = build_checkout_error_widget(str(exc))
        copy_text = "Falha ao gerar o link do webcheckout."

    await server.store.save_thread(thread, context=context)
    async for event in _stream_checkout_widget(
        server, thread, context, widget, copy_text
    ):
        yield event


async def _handle_saved_card_payment(
    server: "StarterChatServer",
    thread: ThreadMetadata,
    context: dict[str, Any],
) -> AsyncIterator[ThreadStreamEvent]:
    card = thread.metadata.get("savedcard_selected_card")
    if not isinstance(card, dict) or not card.get("card_id"):
        widget = build_payment_result_widget(
            False, "Nenhum cartao selecionado para o pagamento."
        )
        async for event in _stream_checkout_widget(
            server, thread, context, widget, "Selecione um cartao para pagar."
        ):
            yield event
        return

    brand = str(card.get("brand") or "Cartao")
    last4 = str(card.get("last4") or "----")

    # Journey 2 is a demonstration flow: no real charge is performed, the
    # payment is always presented as concluded.
    message = (
        f"Pagamento de R$ 0,01 concluido (demonstracao) com o cartao "
        f"{brand} final {last4}."
    )
    widget = build_payment_result_widget(True, message)

    async for event in _stream_checkout_widget(
        server, thread, context, widget, "Resultado do pagamento."
    ):
        yield event


def _detect_card_brand(card_number: str) -> str:
    digits = "".join(ch for ch in card_number if ch.isdigit())
    if not digits:
        return "Cartao"
    if digits.startswith("4"):
        return "Visa"
    if digits[:2] in {"51", "52", "53", "54", "55"} or (
        len(digits) >= 4 and 2221 <= int(digits[:4]) <= 2720
    ):
        return "Mastercard"
    if digits[:2] in {"34", "37"}:
        return "Amex"
    if digits[:4] in {"6011"} or digits[:2] == "65":
        return "Discover"
    return "Cartao"


def _last_four(card_number: str) -> str:
    digits = "".join(ch for ch in card_number if ch.isdigit())
    return digits[-4:] if len(digits) >= 4 else (digits or "----")


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _extract_form_values(payload: dict[str, Any]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []

    for key in ("formData", "form_data", "form", "values", "fields", "data"):
        value = payload.get(key)
        if isinstance(value, dict):
            candidates.append(value)

    fields_list = payload.get("fields")
    if isinstance(fields_list, list):
        list_values: dict[str, Any] = {}
        for item in fields_list:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            if "value" in item:
                list_values[name] = item.get("value")
        if list_values:
            candidates.append(list_values)

    # Some clients merge fields at the root payload.
    root_values = {
        key: value
        for key, value in payload.items()
        if key
        not in {
            "flow",
            "target",
            "checkoutRequest",
            "status",
            "formData",
            "form_data",
            "form",
            "values",
            "fields",
            "data",
        }
        and not isinstance(value, dict)
    }
    if root_values:
        candidates.append(root_values)

    merged: dict[str, Any] = {}
    for candidate in candidates:
        merged.update(candidate)
    return merged


def _parse_customer_values(values: dict[str, Any]) -> dict[str, Any]:
    required = [
        "customer_name",
        "email",
        "document_number",
        "phone_number",
        "street",
        "number",
        "district",
        "city",
        "state",
        "postal_code",
        "country",
    ]

    customer_data = {key: str(values.get(key, "")).strip() for key in required}
    missing = [field for field, value in customer_data.items() if not value]
    if missing:
        raise ValueError(
            f"Campos obrigatorios ausentes: {', '.join(sorted(missing))}"
        )

    email = customer_data["email"].lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ValueError("Email invalido")

    phone_digits = "".join(ch for ch in customer_data["phone_number"] if ch.isdigit())
    if len(phone_digits) < 10 or len(phone_digits) > 15:
        raise ValueError("Telefone deve ter entre 10 e 15 digitos")

    document_digits = "".join(
        ch for ch in customer_data["document_number"] if ch.isdigit()
    )
    if len(document_digits) not in (11, 14):
        raise ValueError("Documento deve ter 11 (CPF) ou 14 (CNPJ) digitos")

    postal_digits = "".join(ch for ch in customer_data["postal_code"] if ch.isdigit())
    if len(postal_digits) < 8:
        raise ValueError("CEP invalido")

    state = customer_data["state"].upper()
    if len(state) != 2 or not state.isalpha():
        raise ValueError("Estado deve ter 2 letras, ex.: SP")

    country = customer_data["country"].upper()
    if len(country) != 2 or not country.isalpha():
        raise ValueError("Pais deve ter 2 letras, ex.: BR")

    customer_data["email"] = email
    customer_data["phone_number"] = phone_digits
    customer_data["document_number"] = document_digits
    customer_data["postal_code"] = postal_digits
    customer_data["state"] = state
    customer_data["country"] = country

    customer_data["document_type"] = "CNPJ" if len(document_digits) == 14 else "CPF"
    customer_data["customer_id"] = customer_data["document_number"]
    return customer_data


def _message_text(item: UserMessageItem) -> str:
    parts: list[str] = []
    for part in item.content:
        text = getattr(part, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return " ".join(parts)


def _latest_user_message(items: list[object]) -> UserMessageItem | None:
    for item in reversed(items):
        if isinstance(item, UserMessageItem):
            return item
    return None


def _checkout_requested(item: UserMessageItem) -> bool:
    message_text = _message_text(item)
    payload_text = item.model_dump_json(exclude_none=True)
    return is_checkout_request(f"{message_text} {payload_text}")
