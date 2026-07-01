"""FastAPI entrypoint for the ChatKit starter backend."""

from __future__ import annotations

from fastapi import HTTPException
from chatkit.server import StreamingResult
from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse

from .checkout import (
    CheckoutFlow,
    CheckoutIntentRequest,
    GetnetClient,
    GetnetWalletClient,
    WalletCardCreateRequest,
    build_demo_request,
)
from .server import StarterChatServer

app = FastAPI(title="ChatKit Starter API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

chatkit_server = StarterChatServer()


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip() or None
    return authorization.strip() or None


@app.get("/wallet/token")
async def get_wallet_access_token() -> JSONResponse:
    try:
        client = GetnetWalletClient.from_env()
        token_info = await client.fetch_access_token()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - surfaced to the UI for debugging
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return JSONResponse(token_info)


@app.post("/checkout/intents")
async def create_checkout_intent(request: CheckoutIntentRequest) -> JSONResponse:
    try:
        client = GetnetClient.from_env()
        result = await client.create_payment_intent(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - surfaced to the UI for debugging
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return JSONResponse(result.model_dump())


@app.post("/checkout/card-registration")
async def create_card_registration_intent() -> JSONResponse:
    """Create a Getnet card-verification intent to register a card via iframe.

    Uses the hosted card-verification flow (checkout_type=IFRAME) so the card
    data is captured on Getnet's page instead of our frontend.
    """
    try:
        client = GetnetClient.from_env()
        request = build_demo_request(CheckoutFlow.CARD_VERIFICATION)
        result = await client.create_payment_intent(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - surfaced to the UI for debugging
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return JSONResponse(result.model_dump())


@app.get("/wallet/cards")
async def list_wallet_cards(
    customer_id: str,
    authorization: str | None = Header(default=None),
) -> JSONResponse:
    try:
        client = GetnetWalletClient.from_env()
        access_token = _extract_bearer_token(authorization)
        result = await client.list_cards(customer_id, access_token=access_token)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - surfaced to the UI for debugging
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return JSONResponse(result)


@app.post("/wallet/cards")
async def create_wallet_card(
    request: WalletCardCreateRequest,
    authorization: str | None = Header(default=None),
) -> JSONResponse:
    try:
        client = GetnetWalletClient.from_env()
        access_token = _extract_bearer_token(authorization)
        result = await client.create_card(request, access_token=access_token)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - surfaced to the UI for debugging
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return JSONResponse(result)


@app.delete("/wallet/cards/{card_id}")
async def delete_wallet_card(
    card_id: str,
    authorization: str | None = Header(default=None),
) -> JSONResponse:
    try:
        client = GetnetWalletClient.from_env()
        access_token = _extract_bearer_token(authorization)
        await client.delete_card(card_id, access_token=access_token)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - surfaced to the UI for debugging
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return JSONResponse({"success": True, "card_id": card_id})


@app.get("/checkout/threads/{thread_id}/latest")
async def get_latest_checkout(thread_id: str) -> JSONResponse:
    try:
        thread = await chatkit_server.store.load_thread(thread_id, context={})
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    latest_checkout = thread.metadata.get("latest_checkout")
    if not isinstance(latest_checkout, dict):
        return JSONResponse({"latest_checkout": None})

    return JSONResponse({"latest_checkout": latest_checkout})

@app.get("/checkout/latest")
async def get_latest_checkout_any_thread() -> JSONResponse:
    latest_checkout: dict | None = None

    for thread in chatkit_server.store.threads.values():
        candidate = thread.metadata.get("latest_checkout")
        if not isinstance(candidate, dict):
            continue

        if latest_checkout is None:
            latest_checkout = candidate
            continue

        current_time = str(latest_checkout.get("updated_at", ""))
        candidate_time = str(candidate.get("updated_at", ""))
        if candidate_time > current_time:
            latest_checkout = candidate

    return JSONResponse({"latest_checkout": latest_checkout})


@app.post("/chatkit")
async def chatkit_endpoint(request: Request) -> Response:
    """Proxy the ChatKit web component payload to the server implementation."""
    payload = await request.body()
    result = await chatkit_server.process(payload, {"request": request})

    if isinstance(result, StreamingResult):
        return StreamingResponse(result, media_type="text/event-stream")
    if hasattr(result, "json"):
        return Response(content=result.json, media_type="application/json")
    return JSONResponse(result)
