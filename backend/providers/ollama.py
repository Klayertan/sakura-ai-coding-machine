import json
from typing import AsyncGenerator, Dict, List, Optional

import httpx

from .base import ChatChunk, InferenceProvider, ModelInfo, ProviderError


class OllamaProvider(InferenceProvider):
    name = 'ollama'

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
        options = {}
        if temperature is not None:
            options['temperature'] = temperature
        if max_tokens is not None:
            options['num_predict'] = max_tokens
        payload = {'model': model, 'messages': messages, 'stream': True}
        if options:
            payload['options'] = options
        try:
            async with self._client.stream('POST', '/api/chat', json=payload) as r:
                if r.status_code != 200:
                    body = (await r.aread()).decode('utf-8', 'replace')
                    # A missing model is the caller's mistake, not a gateway fault.
                    status = 404 if r.status_code == 404 else 502
                    raise ProviderError(_error_detail(body, r.status_code), status)
                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if 'error' in data:
                        raise ProviderError(f"Ollama error: {data['error']}")
                    msg = data.get('message') or {}
                    done = bool(data.get('done'))
                    yield ChatChunk(
                        content=msg.get('content') or '',
                        thinking=msg.get('thinking') or '',
                        done=done,
                        model=data.get('model', model),
                        usage=_usage(data) if done else {},
                    )
                    if done:
                        return
        except httpx.HTTPError as e:
            raise ProviderError(f'Cannot reach Ollama: {type(e).__name__}: {e}') from e
        except json.JSONDecodeError as e:
            raise ProviderError(f'Malformed response from Ollama: {e}') from e
        raise ProviderError('Ollama closed the stream before finishing the reply')

    async def list_models(self) -> List[ModelInfo]:
        try:
            r = await self._client.get('/api/tags', timeout=20.0)
            r.raise_for_status()
            return [ModelInfo(name=m['name'], size_bytes=m.get('size'))
                    for m in r.json().get('models', [])]
        except (httpx.HTTPError, ValueError, KeyError) as e:
            raise ProviderError(f'Cannot list Ollama models: {type(e).__name__}: {e}') from e

    async def health(self) -> bool:
        try:
            return (await self._client.get('/api/tags', timeout=5.0)).is_success
        except httpx.HTTPError:
            return False

    async def aclose(self) -> None:
        await self._client.aclose()


def _usage(data: dict) -> Dict[str, int]:
    return {
        'prompt_tokens': int(data.get('prompt_eval_count') or 0),
        'completion_tokens': int(data.get('eval_count') or 0),
        # Generation time only, so tokens/sec = completion_tokens / (ms / 1000).
        'completion_ms': int((data.get('eval_duration') or 0) / 1e6),
    }


def _error_detail(body: str, status: int) -> str:
    try:
        return f"Ollama error: {json.loads(body)['error']}"
    except (ValueError, KeyError, TypeError):
        return f'Ollama returned HTTP {status}: {body[:300]}'
