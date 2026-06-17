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
    build_checkout_flow_selector_widget,
    build_checkout_error_widget,
    build_checkout_review_widget,
    build_checkout_result_widget,
    build_customer_form_widget,
    build_iframe_feedback_widget,
    build_payment_form_widget,
    build_request_from_journey_data,
    is_checkout_request,
    normalize_flow,
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
            widget = build_checkout_flow_selector_widget()
            async for event in stream_widget(
                thread,
                widget,
                copy_text="Escolha uma alternativa de checkout para continuar.",
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
        thread.metadata["latest_checkout"] = {
            "payment_intent_id": result.payment_intent_id,
            "redirect_url": result.redirect_url,
            "flow": result.flow.value,
            "status": "created",
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
