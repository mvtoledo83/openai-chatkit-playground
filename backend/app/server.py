"""ChatKit server that streams responses from a single assistant."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, AsyncIterator

from chatkit.server import ChatKitServer, stream_widget

from agents import Runner
from chatkit.agents import AgentContext, simple_to_agent_input, stream_agent_response
from chatkit.types import Action, ThreadMetadata, ThreadStreamEvent, UserMessageItem, WidgetItem

from .checkout import (
    CheckoutIntentRequest,
    GetnetClient,
    build_checkout_error_widget,
    build_checkout_result_widget,
    build_checkout_widget,
    is_checkout_request,
)
from .memory_store import MemoryStore
from agents import Agent


MAX_RECENT_ITEMS = 30
MODEL = "gpt-4.1-mini"


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
            widget = build_checkout_widget()
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

        if action.type != "checkout.launch":
            return

        try:
            payload = action.payload if isinstance(action.payload, dict) else {}
            checkout_payload = payload.get("checkoutRequest")
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
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await self.store.save_thread(thread, context=context)
        except Exception as exc:
            widget = build_checkout_error_widget(str(exc))
            copy_text = "Falha ao iniciar checkout"

        async for event in stream_widget(
            thread,
            widget,
            copy_text=copy_text,
            generate_id=lambda item_type: self.store.generate_item_id(
                item_type, thread, context
            ),
        ):
            yield event


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
