import json
import time
from typing import AsyncGenerator, Dict, List, Optional

import httpx

from .base import ChatChunk, InferenceProvider, ModelInfo, ProviderError, Relay


class OpenAIRelayMixin:
    """Forwards an OpenAI chat request unchanged. Needs self._client and self.name."""

    async def relay_chat(self, payload: dict) -> Relay:
        request = self._client.build_request('POST', '/v1/chat/completions', json=payload)
        try:
            response = await self._client.send(request, stream=True)
        except httpx.HTTPError as e:
            raise ProviderError(f'Cannot reach {self.name}: {type(e).__name__}: {e}') from e
        return Relay(
            status_code=response.status_code,
            content_type=response.headers.get('content-type', 'application/json'),
            chunks=_raw_bytes(response),
            close=response.aclose,
        )


async def _raw_bytes(response: httpx.Response) -> AsyncGenerator[bytes, None]:
    try:
        async for chunk in response.aiter_raw():
            yield chunk
    except httpx.HTTPError as e:
        raise ProviderError(f'Provider stream failed: {type(e).__name__}: {e}') from e


class OpenAICompatProvider(OpenAIRelayMixin, InferenceProvider):
    """Any server with /v1/chat/completions, such as llama-server or vLLM."""

    name = 'openai'

    def __init__(self, base_url: str, read_timeout: float = 900.0,
                 transport: Optional[httpx.AsyncBaseTransport] = None):
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(connect=5.0, read=read_timeout, write=30.0, pool=5.0),
            transport=transport,
        )

    async def chat_stream(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[ChatChunk, None]:
        payload = {'model': model, 'messages': messages, 'stream': True,
                   'stream_options': {'include_usage': True}}
        if temperature is not None:
            payload['temperature'] = temperature
        if max_tokens is not None:
            payload['max_tokens'] = max_tokens
        usage = {}
        first_token_at = None
        try:
            async with self._client.stream('POST', '/v1/chat/completions', json=payload) as r:
                if r.status_code != 200:
                    body = (await r.aread()).decode('utf-8', 'replace')
                    # A missing model is the caller's mistake, not a gateway fault.
                    status = 404 if r.status_code == 404 else 502
                    raise ProviderError(_error_detail(body, r.status_code), status)
                async for line in r.aiter_lines():
                    if not line.startswith('data:'):
                        continue
                    data = line[len('data:'):].strip()
                    if data == '[DONE]':
                        if first_token_at is not None:
                            usage['completion_ms'] = int((time.monotonic() - first_token_at) * 1000)
                        yield ChatChunk(done=True, model=model, usage=usage)
                        return
                    event = json.loads(data)
                    if event.get('error'):
                        raise ProviderError(f"Provider error: {event['error']}")
                    if event.get('usage'):
                        usage = {'prompt_tokens': int(event['usage'].get('prompt_tokens') or 0),
                                 'completion_tokens': int(event['usage'].get('completion_tokens') or 0)}
                    for choice in event.get('choices') or []:
                        delta = choice.get('delta') or {}
                        content = delta.get('content') or ''
                        # llama-server and older vLLM use reasoning_content, newer vLLM reasoning.
                        thinking = delta.get('reasoning_content') or delta.get('reasoning') or ''
                        if content or thinking:
                            first_token_at = first_token_at or time.monotonic()
                            yield ChatChunk(content=content, thinking=thinking, model=model)
        except httpx.HTTPError as e:
            raise ProviderError(f'Cannot reach provider: {type(e).__name__}: {e}') from e
        except json.JSONDecodeError as e:
            raise ProviderError(f'Malformed response from provider: {e}') from e
        raise ProviderError('Provider closed the stream before finishing the reply')

    async def list_models(self) -> List[ModelInfo]:
        try:
            r = await self._client.get('/v1/models', timeout=20.0)
            r.raise_for_status()
            return [ModelInfo(name=m['id']) for m in r.json().get('data', [])]
        except (httpx.HTTPError, ValueError, KeyError) as e:
            raise ProviderError(f'Cannot list provider models: {type(e).__name__}: {e}') from e

    async def health(self) -> bool:
        try:
            return (await self._client.get('/v1/models', timeout=5.0)).is_success
        except httpx.HTTPError:
            return False

    async def aclose(self) -> None:
        await self._client.aclose()


def _error_detail(body: str, status: int) -> str:
    try:
        return f"Provider error: {json.loads(body)['error']['message']}"
    except (ValueError, KeyError, TypeError):
        return f'Provider returned HTTP {status}: {body[:300]}'
