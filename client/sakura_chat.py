#!/usr/bin/env python3
import argparse, os, requests

p = argparse.ArgumentParser()
p.add_argument('prompt', nargs='+')
p.add_argument('--url', default=os.getenv('SAKURA_AI_URL', 'https://YOUR-DOK-ENDPOINT'))
p.add_argument('--key', default=os.getenv('SAKURA_AI_API_KEY', ''))
p.add_argument('--model', default=None)
a = p.parse_args()
headers = {'Authorization': f'Bearer {a.key}'} if a.key else {}
r = requests.post(a.url.rstrip('/') + '/api/chat', headers=headers, json={
    'model': a.model,
    'messages': [{'role':'user','content':' '.join(a.prompt)}]
}, timeout=600)
r.raise_for_status()
print(r.json()['message']['content'])
