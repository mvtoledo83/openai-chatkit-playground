"""FastAPI entrypoint for the ChatKit starter backend."""

from __future__ import annotations

from fastapi import HTTPException
from chatkit.server import StreamingResult
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse

from .checkout import CheckoutIntentRequest, GetnetClient
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
