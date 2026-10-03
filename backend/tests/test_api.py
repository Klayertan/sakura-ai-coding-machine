import json

import pytest
from fastapi.testclient import TestClient

from app import Activity, create_app
from config import ConfigError, Settings
from providers import ChatChunk, InferenceProvider, ModelInfo, ProviderError

KEY = 'test-key-0123456789abcdef'
AUTH = {'Authorization': f'Bearer {KEY}'}


class FakeProvider(InferenceProvider):
    name = 'fake'

    def __init__(self, chunks=None, fail_at=None, error=None, models_ok=True):
        self.chunks = chunks if chunks is not None else [
            ChatChunk(thinking='hmm'),
            ChatChunk(content='Hel'),
            ChatChunk(content='lo'),
            ChatChunk(done=True, model='m1', usage={'prompt_tokens': 3, 'completion_tokens': 2}),
        ]
        self.fail_at = fail_at
        self.error = error or ProviderError('boom')
        self.models_ok = models_ok
        self.calls = []
        self.closed = False

    async def chat_stream(self, model, messages, temperature=None, max_tokens=None):
        self.calls.append({'model': model, 'messages': messages,
                           'temperature': temperature, 'max_tokens': max_tokens})
        for i, c in enumerate(self.chunks):
            if self.fail_at == i:
                raise self.error
            yield c

    async def list_models(self):
        if not self.models_ok:
            raise ProviderError('down')
        return [ModelInfo('m1', 123), ModelInfo('other')]

    async def health(self):
        return self.models_ok

    async def aclose(self):
        self.closed = True


def make_client(provider=None, **overrides):
    settings = Settings(api_key=KEY, default_model='m1', gpu_yen_per_hour=1008,
                        idle_shutdown_minutes=0, task_id='task-1', **overrides)
    provider = provider or FakeProvider()
    app = create_app(settings, provider, gpu_probe=lambda: {'name': 'H100'})
    return TestClient(app), provider


def chat_body(**extra):
    return {'messages': [{'role': 'user', 'content': 'hi'}], **extra}


def ndjson(response):
    return [json.loads(l) for l in response.text.splitlines() if l]


# --- configuration / fail-closed auth ---------------------------------------

@pytest.mark.parametrize('key', ['', 'short', 'dev-only-change-me',
                                 'replace-with-a-long-random-secret'])
def test_refuses_to_start_without_real_key(key):
    with pytest.raises(ConfigError):
        create_app(Settings(api_key=key), FakeProvider())


def test_allow_no_auth_is_explicit_opt_in():
    client = TestClient(create_app(Settings(allow_no_auth=True, idle_shutdown_minutes=0),
                                   FakeProvider()))
    assert client.get('/api/models').status_code == 200


def test_settings_from_env():
    s = Settings.from_env({'SAKURA_AI_API_KEY': ' k ', 'GPU_YEN_PER_HOUR': '5',
                           'OLLAMA_URL': 'http://x:1/', 'SAKURA_TASK_ID': 't'})
    assert (s.api_key, s.gpu_yen_per_hour, s.ollama_url, s.task_id) == ('k', 5.0, 'http://x:1', 't')
    assert Settings.from_env({}).gpu_yen_per_hour == 1008.0
    assert Settings.from_env({'GATEWAY_API_KEY': 'alt'}).api_key == 'alt'
    with pytest.raises(ConfigError):
        Settings.from_env({'VOUCHER_YEN': 'lots'})


@pytest.mark.parametrize('headers', [{}, {'Authorization': 'Bearer wrong'},
                                     {'Authorization': KEY}, {'Authorization': 'Bearer '}])
@pytest.mark.parametrize('method,path', [('get', '/api/models'), ('get', '/api/usage'),
                                         ('post', '/api/chat')])
def test_protected_endpoints_reject_bad_auth(headers, method, path):
    client, provider = make_client()
    kwargs = {'json': chat_body()} if method == 'post' else {}
    r = getattr(client, method)(path, headers=headers, **kwargs)
    assert r.status_code == 401
    assert provider.calls == []


def test_docs_are_not_exposed():
    client, _ = make_client()
    assert client.get('/docs').status_code == 404
    assert client.get('/openapi.json').status_code == 404


# --- health / models / usage -------------------------------------------------

def test_health_is_public_and_minimal():
    client, _ = make_client()
    assert client.get('/health').json() == {'ok': True, 'provider_ok': True, 'model_ready': True}


def test_health_reports_provider_down_and_missing_model():
    client, _ = make_client(FakeProvider(models_ok=False))
    assert client.get('/health').json() == {'ok': True, 'provider_ok': False, 'model_ready': False}
    client = TestClient(create_app(Settings(api_key=KEY, default_model='absent',
                                            idle_shutdown_minutes=0), FakeProvider()))
    assert client.get('/health').json()['model_ready'] is False


def test_models():
    client, _ = make_client()
    assert client.get('/api/models', headers=AUTH).json() == {
        'provider': 'fake', 'default_model': 'm1',
        'models': [{'name': 'm1', 'size_bytes': 123}, {'name': 'other', 'size_bytes': None}],
    }


def test_models_provider_down_is_502():
    client, _ = make_client(FakeProvider(models_ok=False))
    r = client.get('/api/models', headers=AUTH)
    assert (r.status_code, r.json()['detail']) == (502, 'down')


def test_usage_estimate():
    client, _ = make_client()
    client.app.state.activity.started_at -= 1800  # pretend half an hour of uptime
    u = client.get('/api/usage', headers=AUTH).json()
    assert u['task_id'] == 'task-1'
    assert 1800 <= u['uptime_seconds'] <= 1802
    assert 504 <= u['estimated_cost_yen'] <= 505
    assert u['estimated_voucher_remaining_yen'] == pytest.approx(100000 - u['estimated_cost_yen'])
    assert u['gpu'] == {'name': 'H100'}


# --- chat ----------------------------------------------------------------------

def test_chat_non_streaming_aggregates():
    client, provider = make_client()
    r = client.post('/api/chat', headers=AUTH, json=chat_body(temperature=0.2, max_tokens=50))
    assert r.status_code == 200
    assert r.json() == {
        'model': 'm1',
        'message': {'role': 'assistant', 'content': 'Hello', 'thinking': 'hmm'},
        'done': True,
        'usage': {'prompt_tokens': 3, 'completion_tokens': 2},
    }
    assert provider.calls == [{'model': 'm1', 'messages': [{'role': 'user', 'content': 'hi'}],
                               'temperature': 0.2, 'max_tokens': 50}]


def test_chat_model_override():
    client, provider = make_client()
    client.post('/api/chat', headers=AUTH, json=chat_body(model='other'))
    assert provider.calls[0]['model'] == 'other'


def test_chat_streaming_ndjson():
    client, _ = make_client()
    r = client.post('/api/chat', headers=AUTH, json=chat_body(stream=True))
    assert r.status_code == 200
    assert r.headers['content-type'].startswith('application/x-ndjson')
    assert ndjson(r) == [
        {'type': 'delta', 'thinking': 'hmm'},
        {'type': 'delta', 'content': 'Hel'},
        {'type': 'delta', 'content': 'lo'},
        {'type': 'done', 'model': 'm1', 'usage': {'prompt_tokens': 3, 'completion_tokens': 2}},
    ]


def test_chat_streaming_keeps_non_ascii_intact():
    client, _ = make_client(FakeProvider([ChatChunk(content='高火力'), ChatChunk(done=True)]))
    r = client.post('/api/chat', headers=AUTH, json=chat_body(stream=True))
    assert ndjson(r)[0] == {'type': 'delta', 'content': '高火力'}


@pytest.mark.parametrize('stream', [False, True])
def test_chat_provider_failure_before_first_token_is_http_error(stream):
    provider = FakeProvider(fail_at=0, error=ProviderError('model not found', 404))
    client, _ = make_client(provider)
    r = client.post('/api/chat', headers=AUTH, json=chat_body(stream=stream))
    assert (r.status_code, r.json()['detail']) == (404, 'model not found')
    assert client.app.state.activity._in_flight == 0


def test_chat_streaming_mid_stream_failure_emits_error_event():
    client, _ = make_client(FakeProvider(fail_at=2))
    r = client.post('/api/chat', headers=AUTH, json=chat_body(stream=True))
    assert r.status_code == 200
    events = ndjson(r)
    assert events[-1] == {'type': 'error', 'detail': 'boom'}
    assert [e['type'] for e in events] == ['delta', 'delta', 'error']
    assert client.app.state.activity._in_flight == 0


@pytest.mark.parametrize('body', [
    {'messages': []},
    {'messages': [{'role': 'tool', 'content': 'x'}]},
    {'messages': [{'role': 'user', 'content': 'x'}], 'temperature': 9},
    {},
])
def test_chat_validation(body):
    client, provider = make_client()
    assert client.post('/api/chat', headers=AUTH, json=body).status_code == 422
    assert provider.calls == []


# --- idle shutdown ---------------------------------------------------------------

def test_activity_idle_tracking(monkeypatch):
    now = [100.0]
    monkeypatch.setattr('app.time.monotonic', lambda: now[0])
    a = Activity()
    now[0] += 50
    assert a.idle_seconds() == 50
    a.begin()
    now[0] += 500
    assert a.idle_seconds() == 0  # never idle while a request is generating
    a.end()
    now[0] += 7
    assert a.idle_seconds() == 7


def test_idle_watchdog_triggers_shutdown(monkeypatch):
    import asyncio
    import app as app_module

    async def no_sleep(_):
        pass

    monkeypatch.setattr(app_module.asyncio, 'sleep', no_sleep)
    activity = Activity()
    monkeypatch.setattr(activity, 'idle_seconds', lambda: 9999)
    fired = []
    asyncio.run(app_module._idle_watchdog(activity, 60, lambda: fired.append(True)))
    assert fired == [True]


def test_lifespan_closes_provider():
    client, provider = make_client()
    with client:
        pass
    assert provider.closed
