import asyncio
import json

import httpx
import pytest

from gpu import parse_nvidia_smi
from providers import OllamaProvider, ProviderError


def provider_with(handler):
    return OllamaProvider('http://ollama.test', transport=httpx.MockTransport(handler))


def collect(provider, **kwargs):
    async def run():
        return [c async for c in provider.chat_stream('m', [{'role': 'user', 'content': 'hi'}],
                                                      **kwargs)]
    return asyncio.run(run())


def lines(*objs):
    return ''.join(json.dumps(o) + '\n' for o in objs).encode()


def test_chat_stream_translates_ollama_ndjson():
    seen = {}

    def handler(request):
        seen['path'] = request.url.path
        seen['body'] = json.loads(request.content)
        return httpx.Response(200, content=lines(
            {'model': 'm', 'message': {'role': 'assistant', 'content': '', 'thinking': 'th'}, 'done': False},
            {'model': 'm', 'message': {'role': 'assistant', 'content': 'Hi'}, 'done': False},
            {'model': 'm', 'message': {'role': 'assistant', 'content': ''}, 'done': True,
             'prompt_eval_count': 11, 'eval_count': 4, 'eval_duration': 2_000_000_000},
        ))

    chunks = collect(provider_with(handler), temperature=0.1, max_tokens=64)
    assert seen['path'] == '/api/chat'
    assert seen['body'] == {'model': 'm', 'messages': [{'role': 'user', 'content': 'hi'}],
                            'stream': True, 'options': {'temperature': 0.1, 'num_predict': 64}}
    assert [(c.content, c.thinking, c.done) for c in chunks] == [
        ('', 'th', False), ('Hi', '', False), ('', '', True)]
    assert chunks[-1].usage == {'prompt_tokens': 11, 'completion_tokens': 4, 'completion_ms': 2000}


def test_chat_stream_omits_options_when_unset():
    seen = {}

    def handler(request):
        seen['body'] = json.loads(request.content)
        return httpx.Response(200, content=lines({'message': {'content': 'x'}, 'done': True}))

    collect(provider_with(handler))
    assert 'options' not in seen['body']


def test_missing_model_maps_to_404():
    p = provider_with(lambda r: httpx.Response(404, json={'error': "model 'm' not found"}))
    with pytest.raises(ProviderError) as e:
        collect(p)
    assert e.value.status_code == 404
    assert "model 'm' not found" in e.value.detail


def test_other_http_errors_map_to_502():
    p = provider_with(lambda r: httpx.Response(500, text='kaboom'))
    with pytest.raises(ProviderError) as e:
        collect(p)
    assert e.value.status_code == 502
    assert 'kaboom' in e.value.detail


def test_inline_error_line_and_truncated_stream():
    p = provider_with(lambda r: httpx.Response(200, content=lines({'error': 'out of memory'})))
    with pytest.raises(ProviderError, match='out of memory'):
        collect(p)
    p = provider_with(lambda r: httpx.Response(200, content=lines(
        {'message': {'content': 'partial'}, 'done': False})))
    with pytest.raises(ProviderError, match='before finishing'):
        collect(p)


def test_connection_failure_is_provider_error():
    def handler(request):
        raise httpx.ConnectError('refused')

    p = provider_with(handler)
    with pytest.raises(ProviderError, match='Cannot reach Ollama'):
        collect(p)
    assert asyncio.run(p.health()) is False
    with pytest.raises(ProviderError):
        asyncio.run(p.list_models())


def test_list_models_and_health():
    p = provider_with(lambda r: httpx.Response(200, json={
        'models': [{'name': 'gpt-oss:20b', 'size': 14}, {'name': 'x'}]}))

    async def run():
        return await p.list_models(), await p.health()

    models, ok = asyncio.run(run())
    assert [(m.name, m.size_bytes) for m in models] == [('gpt-oss:20b', 14), ('x', None)]
    assert ok is True


def test_parse_nvidia_smi():
    assert parse_nvidia_smi('NVIDIA H100 80GB HBM3, 14231, 81559, 37\n') == {
        'name': 'NVIDIA H100 80GB HBM3', 'memory_used_mb': 14231,
        'memory_total_mb': 81559, 'utilization_percent': 37}
    assert parse_nvidia_smi('') is None
    assert parse_nvidia_smi('garbage') is None
    assert parse_nvidia_smi('H100, [N/A], 81559, 0') is None
