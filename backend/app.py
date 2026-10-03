import os, time
from typing import List, Literal
import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434')
API_KEY = os.getenv('SAKURA_AI_API_KEY', '')
DEFAULT_MODEL = os.getenv('OLLAMA_MODEL', 'gpt-oss:20b')
VOUCHER_YEN = float(os.getenv('VOUCHER_YEN', '100000'))
GPU_YEN_PER_HOUR = float(os.getenv('GPU_YEN_PER_HOUR', '0'))
STARTED_AT = time.time()

app = FastAPI(title='Sakura AI Coding Machine', version='0.1.0')

class Message(BaseModel):
    role: Literal['system','user','assistant']
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    model: str | None = None
    stream: bool = False


def auth(authorization: str | None):
    if not API_KEY:
        return
    if authorization != f'Bearer {API_KEY}':
        raise HTTPException(status_code=401, detail='Invalid API key')

@app.get('/health')
async def health():
    async with httpx.AsyncClient(timeout=5) as c:
        try:
            r = await c.get(f'{OLLAMA_URL}/api/tags')
            ollama_ok = r.is_success
        except Exception:
            ollama_ok = False
    elapsed_h = (time.time() - STARTED_AT) / 3600
    est_cost = elapsed_h * GPU_YEN_PER_HOUR
    return {
        'ok': True,
        'ollama_ok': ollama_ok,
        'default_model': DEFAULT_MODEL,
        'uptime_hours': round(elapsed_h, 4),
        'estimated_cost_yen': round(est_cost, 2),
        'voucher_yen': VOUCHER_YEN,
        'estimated_voucher_remaining_yen': round(max(0, VOUCHER_YEN - est_cost), 2),
    }

@app.get('/api/models')
async def models(authorization: str | None = Header(default=None)):
    auth(authorization)
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f'{OLLAMA_URL}/api/tags')
        r.raise_for_status()
        return r.json()

@app.post('/api/chat')
async def chat(req: ChatRequest, authorization: str | None = Header(default=None)):
    auth(authorization)
    payload = {
        'model': req.model or DEFAULT_MODEL,
        'messages': [m.model_dump() for m in req.messages],
        'stream': req.stream,
    }
    if req.stream:
        raise HTTPException(status_code=501, detail='Streaming is planned for v0.2')
    async with httpx.AsyncClient(timeout=None) as c:
        r = await c.post(f'{OLLAMA_URL}/api/chat', json=payload)
        r.raise_for_status()
        return r.json()
