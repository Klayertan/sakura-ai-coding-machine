import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import create_app
from config import Settings
from providers import OllamaProvider, OpenAICompatProvider, ProviderError, build_provider

KEY = 'test-key-0123456789abcdef'
AUTH = {'Authorization': f'Bearer {KEY}'}

TOOL_CALL = {'tool_calls': [{'index': 0, 'id': 'call_1', 'type': 'function',
                             'function': {'name': 'read_file', 'arguments': '{"path":"a.py"}'}}]}


def sse(*events, done=True):
    lines = [f'data: {json.dumps(e)}\n\n' for e in events]
    if done:
        lines.append('data: [DONE]\n\n')
    return ''.join(lines).encode()


class Body(httpx.AsyncByteStream):
    """Unread like a real network body; httpx.Response(content=...) counts as consumed."""

    def __init__(self, content):
        self.content = content

    async def __aiter__(self):
        yield self.content


def delta(**fields):
    return {'choices': [{'index': 0, 'delta': fields}]}


def provider_with(handler):
    return OpenAICompatProvider('http://upstream', transport=httpx.MockTransport(handler))


def collect(provider, model='m1'):
    async def run():
        return [c async for c in provider.chat_stream(model, [{'role': 'user', 'content': 'hi'}])]
    return asyncio.run(run())


def make_client(handler, **overrides):
    settings = Settings(api_key=KEY, default_model='m1', idle_shutdown_minutes=0, **overrides)
    app = create_app(settings, provider_with(handler), gpu_probe=lambda: None)
    return TestClient(app), app


# --- provider ----------------------------------------------------------------

def test_stream_maps_content_thinking_and_usage():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, content=sse(
            delta(reasoning_content='hmm'), delta(reasoning='more'), delta(content='Hi'),
            {'choices': [], 'usage': {'prompt_tokens': 3, 'completion_tokens': 2}},
        ))

    chunks = collect(provider_with(handler))
    assert seen['stream'] is True and seen['stream_options'] == {'include_usage': True}
    assert [c.thinking for c in chunks[:2]] == ['hmm', 'more']
    assert chunks[2].content == 'Hi'
    assert chunks[-1].done
    assert chunks[-1].usage['prompt_tokens'] == 3
    assert chunks[-1].usage['completion_tokens'] == 2
    assert 'completion_ms' in chunks[-1].usage


def test_stream_without_done_marker_is_an_error():
    handler = lambda request: httpx.Response(200, content=sse(delta(content='Hi'), done=False))
    with pytest.raises(ProviderError, match='closed the stream'):
        collect(provider_with(handler))


def test_unknown_model_is_a_404():
    handler = lambda request: httpx.Response(404, json={'error': {'message': 'no such model'}})
    with pytest.raises(ProviderError, match='no such model') as e:
        collect(provider_with(handler))
    assert e.value.status_code == 404


def test_unreachable_server_is_a_provider_error():
    def handler(request):
        raise httpx.ConnectError('refused')

    provider = provider_with(handler)
    with pytest.raises(ProviderError, match='Cannot reach'):
        collect(provider)
    assert asyncio.run(provider.health()) is False


def test_list_models():
    handler = lambda request: httpx.Response(200, json={'data': [{'id': 'm1'}, {'id': 'm2'}]})
    models = asyncio.run(provider_with(handler).list_models())
    assert [m.name for m in models] == ['m1', 'm2']


def test_build_provider_selects_openai():
    assert isinstance(build_provider(Settings(provider='openai')), OpenAICompatProvider)


def test_inference_model_wins_over_ollama_model():
    settings = Settings.from_env({'INFERENCE_MODEL': 'deepseek', 'OLLAMA_MODEL': 'gpt-oss:20b'})
    assert settings.default_model == 'deepseek'
    assert Settings.from_env({'OLLAMA_MODEL': 'gpt-oss:20b'}).default_model == 'gpt-oss:20b'


# --- gateway passthrough -----------------------------------------------------

def test_passthrough_requires_auth():
    client, _ = make_client(lambda request: httpx.Response(200, json={}))
    assert client.post('/v1/chat/completions', json={}).status_code == 401
    assert client.get('/v1/models').status_code == 401


def test_passthrough_keeps_tools_and_streamed_tool_calls():
    seen = {}
    stream = sse(delta(**TOOL_CALL))

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, stream=Body(stream), headers={'content-type': 'text/event-stream'})

    client, _ = make_client(handler)
    tools = [{'type': 'function', 'function': {'name': 'read_file', 'parameters': {}}}]
    messages = [{'role': 'tool', 'tool_call_id': 'call_1', 'content': 'x = 1'}]
    r = client.post('/v1/chat/completions', headers=AUTH,
                    json={'messages': messages, 'tools': tools, 'stream': True})
    assert r.status_code == 200
    assert r.headers['content-type'].startswith('text/event-stream')
    assert r.content == stream
    assert seen['tools'] == tools and seen['messages'] == messages
    assert seen['model'] == 'm1'  # the default fills in when the agent names none


def test_passthrough_keeps_upstream_errors():
    error = json.dumps({'error': {'message': 'bad request'}}).encode()
    handler = lambda request: httpx.Response(400, stream=Body(error))
    client, _ = make_client(handler)
    r = client.post('/v1/chat/completions', headers=AUTH, json={'model': 'x', 'messages': []})
    assert r.status_code == 400
    assert r.json()['error']['message'] == 'bad request'


@pytest.mark.parametrize('body', [b'not json', b'[1, 2]'])
def test_passthrough_rejects_bad_bodies(body):
    client, _ = make_client(lambda request: httpx.Response(200, json={}))
    assert client.post('/v1/chat/completions', headers=AUTH, content=body).status_code == 400


def test_passthrough_provider_down_is_502_and_clears_activity():
    def handler(request):
        raise httpx.ConnectError('refused')

    client, app = make_client(handler)
    assert client.post('/v1/chat/completions', headers=AUTH, json={}).status_code == 502
    assert app.state.activity._in_flight == 0


def test_passthrough_stream_failure_clears_activity():
    class Broken(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {}\n\n'
            raise httpx.ReadError('lost')

    client, app = make_client(lambda request: httpx.Response(200, stream=Broken()))
    r = client.post('/v1/chat/completions', headers=AUTH, json={'stream': True})
    assert r.content == b'data: {}\n\n'
    assert app.state.activity._in_flight == 0


def test_relay_closes_upstream_when_client_disconnects():
    closed = []

    class Tracked(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'first'
            yield b'second'

        async def aclose(self):
            closed.append(True)

    async def run():
        provider = provider_with(lambda request: httpx.Response(200, stream=Tracked()))
        relay = await provider.relay_chat({'model': 'm1'})
        await relay.chunks.__anext__()
        await relay.close()

    asyncio.run(run())
    assert closed == [True]


def test_openai_models_listing():
    handler = lambda request: httpx.Response(200, json={'data': [{'id': 'm1'}]})
    client, _ = make_client(handler)
    assert client.get('/v1/models', headers=AUTH).json()['data'][0]['id'] == 'm1'


def test_health_reports_model_ready_for_aliased_model():
    handler = lambda request: httpx.Response(200, json={'data': [{'id': 'm1'}]})
    client, _ = make_client(handler)
    assert client.get('/health').json() == {'ok': True, 'provider_ok': True, 'model_ready': True}


def test_ollama_relays_to_its_openai_endpoint():
    paths = []

    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(200, json={'ok': True})

    async def run():
        provider = OllamaProvider('http://upstream', transport=httpx.MockTransport(handler))
        relay = await provider.relay_chat({'model': 'm1'})
        await relay.close()
        return relay.status_code

    assert asyncio.run(run()) == 200
    assert paths == ['/v1/chat/completions']
