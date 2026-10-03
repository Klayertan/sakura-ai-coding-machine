"""Authenticated gateway in front of the inference provider.

This is the only port exposed through the Sakura DOK HTTPS endpoint; the
provider (Ollama) listens on loopback only.
"""
import asyncio
import hmac
import json
import logging
import os
import signal
import time
from contextlib import asynccontextmanager
from typing import Callable, List, Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import Settings
from gpu import gpu_stats
from providers import ChatChunk, InferenceProvider, ProviderError, build_provider

log = logging.getLogger('sakura_ai')


class Message(BaseModel):
    role: Literal['system', 'user', 'assistant']
    content: str


class ChatRequest(BaseModel):
    messages: List[Message] = Field(min_length=1)
    model: Optional[str] = None
    stream: bool = False
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=None, gt=0)


class Activity:
    """Tracks uptime and idleness for cost estimation and idle shutdown."""

    def __init__(self):
        self.started_at = time.time()
        self._last = time.monotonic()
        self._in_flight = 0

    def touch(self):
        self._last = time.monotonic()

    def begin(self):
        self._in_flight += 1

    def end(self):
        self._in_flight -= 1
        self.touch()

    def idle_seconds(self) -> float:
        return 0.0 if self._in_flight > 0 else time.monotonic() - self._last


def _terminate():
    # uvicorn handles SIGTERM gracefully; when it exits the DOK task ends and billing stops.
    os.kill(os.getpid(), signal.SIGTERM)


async def _idle_watchdog(activity: Activity, limit_seconds: float, shutdown: Callable[[], None]):
    while True:
        await asyncio.sleep(min(30.0, limit_seconds / 2))
        if activity.idle_seconds() >= limit_seconds:
            log.warning('Idle for %.0f min; shutting down to stop GPU billing.', limit_seconds / 60)
            shutdown()
            return


def _ndjson(obj: dict) -> bytes:
    return (json.dumps(obj, ensure_ascii=False) + '\n').encode('utf-8')


def create_app(
    settings: Optional[Settings] = None,
    provider: Optional[InferenceProvider] = None,
    gpu_probe: Callable[[], Optional[dict]] = gpu_stats,
    shutdown: Callable[[], None] = _terminate,
) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.validate()
    provider = provider or build_provider(settings)
    activity = Activity()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        watchdog = None
        if settings.idle_shutdown_minutes > 0:
            watchdog = asyncio.create_task(
                _idle_watchdog(activity, settings.idle_shutdown_minutes * 60, shutdown)
            )
        yield
        if watchdog:
            watchdog.cancel()
        await provider.aclose()

    # Interactive docs are disabled: nothing unauthenticated beyond /health.
    app = FastAPI(title='Sakura AI Coding Machine', version='0.2.0', lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.activity = activity

    def require_auth(authorization: Optional[str] = Header(default=None)):
        if settings.api_key:
            expected = f'Bearer {settings.api_key}'.encode()
            if not hmac.compare_digest((authorization or '').encode(), expected):
                raise HTTPException(status_code=401, detail='Invalid or missing API key',
                                    headers={'WWW-Authenticate': 'Bearer'})
        activity.touch()

    @app.get('/health')
    async def health():
        """Unauthenticated liveness probe. Deliberately reveals no cost or model details."""
        try:
            names = [m.name for m in await provider.list_models()]
            return {'ok': True, 'provider_ok': True, 'model_ready': settings.default_model in names}
        except ProviderError:
            return {'ok': True, 'provider_ok': False, 'model_ready': False}

    @app.get('/api/models', dependencies=[Depends(require_auth)])
    async def models():
        try:
            found = await provider.list_models()
        except ProviderError as e:
            raise HTTPException(status_code=e.status_code, detail=e.detail)
        return {
            'provider': provider.name,
            'default_model': settings.default_model,
            'models': [{'name': m.name, 'size_bytes': m.size_bytes} for m in found],
        }

    @app.get('/api/usage', dependencies=[Depends(require_auth)])
    async def usage():
        """Estimate for THIS task only: uptime x configured rate. Not Sakura billing data."""
        uptime = time.time() - activity.started_at
        cost = uptime / 3600 * settings.gpu_yen_per_hour
        return {
            'task_id': settings.task_id or None,
            'uptime_seconds': round(uptime),
            'gpu_yen_per_hour': settings.gpu_yen_per_hour,
            'estimated_cost_yen': round(cost, 2),
            'voucher_yen': settings.voucher_yen,
            'estimated_voucher_remaining_yen': round(max(0.0, settings.voucher_yen - cost), 2),
            'idle_seconds': round(activity.idle_seconds()),
            'idle_shutdown_minutes': settings.idle_shutdown_minutes,
            'gpu': await asyncio.to_thread(gpu_probe),
        }

    @app.post('/api/chat', dependencies=[Depends(require_auth)])
    async def chat(req: ChatRequest):
        model = req.model or settings.default_model
        chunks = provider.chat_stream(
            model, [m.model_dump() for m in req.messages], req.temperature, req.max_tokens
        )
        activity.begin()

        if not req.stream:
            content, thinking, last = [], [], ChatChunk(model=model)
            try:
                async for c in chunks:
                    content.append(c.content)
                    thinking.append(c.thinking)
                    last = c
            except ProviderError as e:
                raise HTTPException(status_code=e.status_code, detail=e.detail)
            finally:
                activity.end()
            message = {'role': 'assistant', 'content': ''.join(content)}
            if any(thinking):
                message['thinking'] = ''.join(thinking)
            return {'model': last.model or model, 'message': message, 'done': True,
                    'usage': last.usage}

        # Pull the first chunk before committing to a 200, so failures such as an
        # unknown model or an unreachable provider surface as real HTTP errors.
        try:
            first = await chunks.__anext__()
        except StopAsyncIteration:
            first = None
        except ProviderError as e:
            activity.end()
            raise HTTPException(status_code=e.status_code, detail=e.detail)

        async def body():
            try:
                c = first
                while c is not None:
                    if c.content or c.thinking:
                        delta = {'type': 'delta'}
                        if c.content:
                            delta['content'] = c.content
                        if c.thinking:
                            delta['thinking'] = c.thinking
                        yield _ndjson(delta)
                    if c.done:
                        yield _ndjson({'type': 'done', 'model': c.model or model, 'usage': c.usage})
                    activity.touch()
                    try:
                        c = await chunks.__anext__()
                    except StopAsyncIteration:
                        c = None
            except ProviderError as e:
                yield _ndjson({'type': 'error', 'detail': e.detail})
            finally:
                # Also runs on client disconnect: closing the provider stream stops generation.
                await chunks.aclose()
                activity.end()

        return StreamingResponse(
            body(),
            media_type='application/x-ndjson',
            headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
        )

    return app
