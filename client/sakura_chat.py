#!/usr/bin/env python3
"""Minimal Mac CLI for the Sakura AI gateway.

    sakura_chat.py explain this segfault      # streams the reply
    sakura_chat.py --usage                    # GPU, runtime and voucher estimate
    sakura_chat.py --models
"""
import argparse
import json
import os
import sys

import requests

CONNECT_TIMEOUT = 10
# Generous read timeout: the first request may wait for the model to load into VRAM.
READ_TIMEOUT = 900


def fail(message):
    sys.exit(f'error: {message}')


def check(r):
    if r.status_code == 401:
        fail('gateway rejected the API key (check SAKURA_AI_API_KEY).')
    if r.status_code == 503:
        fail('gateway not ready (HTTP 503). The DOK container may still be starting '
             'or pulling the model; retry shortly.')
    if not r.ok:
        try:
            detail = r.json().get('detail')
        except ValueError:
            detail = r.text[:300]
        fail(f'HTTP {r.status_code}: {detail}')
    return r


def stream_chat(session, url, payload, show_thinking):
    payload['stream'] = True
    with session.post(url, json=payload, stream=True,
                      timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)) as r:
        check(r)
        r.encoding = 'utf-8'
        finished = False
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            event = json.loads(line)
            if event['type'] == 'delta':
                if show_thinking and event.get('thinking'):
                    sys.stderr.write(event['thinking'])
                    sys.stderr.flush()
                sys.stdout.write(event.get('content', ''))
                sys.stdout.flush()
            elif event['type'] == 'done':
                finished = True
                print()
                usage = event.get('usage') or {}
                ms, tokens = usage.get('completion_ms'), usage.get('completion_tokens')
                if ms and tokens:
                    print(f"[{event.get('model')}: {tokens} tokens, "
                          f"{tokens / (ms / 1000):.1f} tok/s]", file=sys.stderr)
            elif event['type'] == 'error':
                print()
                fail(event.get('detail'))
        if not finished:
            fail('stream ended before the reply was complete.')


def print_usage(u):
    gpu = u.get('gpu')
    if gpu:
        print(f"GPU:      {gpu['name']}  "
              f"{gpu['memory_used_mb'] / 1024:.1f} / {gpu['memory_total_mb'] / 1024:.1f} GB  "
              f"({gpu['utilization_percent']}% util)")
    else:
        print('GPU:      not detected')
    h, rem = divmod(int(u['uptime_seconds']), 3600)
    print(f"Runtime:  {h}h {rem // 60:02d}m  (this task)")
    print(f"Spend:    ~¥{u['estimated_cost_yen']:,.0f} at ¥{u['gpu_yen_per_hour']:,.0f}/h (estimate)")
    print(f"Voucher:  ~¥{u['estimated_voucher_remaining_yen']:,.0f} / ¥{u['voucher_yen']:,.0f} "
          f"(this task only)")
    if u.get('idle_shutdown_minutes'):
        left = u['idle_shutdown_minutes'] - u['idle_seconds'] / 60
        print(f"Idle:     auto-shutdown after {left:.0f} more idle minutes")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('prompt', nargs='*')
    p.add_argument('--url', default=os.getenv('SAKURA_AI_URL', ''))
    p.add_argument('--key', default=os.getenv('SAKURA_AI_API_KEY', ''))
    p.add_argument('--model', default=None)
    p.add_argument('--system', default=None, help='system prompt')
    p.add_argument('--no-stream', action='store_true', help='wait for the full reply')
    p.add_argument('--thinking', action='store_true', help='show model reasoning on stderr')
    p.add_argument('--models', action='store_true', help='list models and exit')
    p.add_argument('--usage', action='store_true', help='show GPU/runtime/voucher estimate and exit')
    p.add_argument('--health', action='store_true', help='check the gateway and exit')
    a = p.parse_args()

    if not a.url:
        fail('set SAKURA_AI_URL (or --url) to the DOK HTTPS endpoint.')
    base = a.url.split('?')[0].rstrip('/')  # tolerate the "?token=" suffix DOK displays
    session = requests.Session()
    if a.key:
        session.headers['Authorization'] = f'Bearer {a.key}'

    try:
        if a.health:
            print(json.dumps(check(session.get(base + '/health', timeout=CONNECT_TIMEOUT)).json()))
        elif a.models:
            data = check(session.get(base + '/api/models', timeout=30)).json()
            for m in data['models']:
                size = f"{m['size_bytes'] / 1e9:.1f} GB" if m.get('size_bytes') else ''
                mark = '*' if m['name'] == data.get('default_model') else ' '
                print(f"{mark} {m['name']:32} {size}")
        elif a.usage:
            print_usage(check(session.get(base + '/api/usage', timeout=30)).json())
        else:
            if not a.prompt:
                p.error('a prompt is required')
            messages = [{'role': 'system', 'content': a.system}] if a.system else []
            messages.append({'role': 'user', 'content': ' '.join(a.prompt)})
            payload = {'model': a.model, 'messages': messages}
            if a.no_stream:
                r = check(session.post(base + '/api/chat', json=payload,
                                       timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)))
                print(r.json()['message']['content'])
            else:
                stream_chat(session, base + '/api/chat', payload, a.thinking)
    except requests.ConnectionError as e:
        fail(f'cannot connect to {base}: {e}')
    except requests.Timeout:
        fail('request timed out.')
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == '__main__':
    main()
