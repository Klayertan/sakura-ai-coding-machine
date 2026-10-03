"""Gateway configuration, read once from environment variables."""
import os
from dataclasses import dataclass
from typing import Mapping, Optional

# Values shipped in .env.example / docs. Never acceptable as a real key.
PLACEHOLDER_KEYS = {'replace-with-a-long-random-secret', 'dev-only-change-me'}
MIN_KEY_LENGTH = 16


class ConfigError(RuntimeError):
    pass


def _flag(value: Optional[str]) -> bool:
    return (value or '').strip().lower() in {'1', 'true', 'yes', 'on'}


@dataclass(frozen=True)
class Settings:
    api_key: str = ''
    allow_no_auth: bool = False
    provider: str = 'ollama'
    ollama_url: str = 'http://127.0.0.1:11434'
    default_model: str = 'gpt-oss:20b'
    voucher_yen: float = 100000.0
    # DOK H100 list price: 0.28 yen/s = 1,008 yen/h, tax included (checked 2026-10).
    gpu_yen_per_hour: float = 1008.0
    # The task is billed per second until the container exits, so exit when idle.
    idle_shutdown_minutes: float = 60.0
    # Max silence from the provider, e.g. while a large model loads into VRAM.
    provider_read_timeout_seconds: float = 900.0
    task_id: str = ''

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> 'Settings':
        env = os.environ if env is None else env
        d = cls()
        try:
            return cls(
                # DOK reserves the SAKURA_ prefix for its own variables, so accept a neutral name too.
                api_key=(env.get('SAKURA_AI_API_KEY') or env.get('GATEWAY_API_KEY', '')).strip(),
                allow_no_auth=_flag(env.get('ALLOW_NO_AUTH')),
                provider=env.get('INFERENCE_PROVIDER', d.provider).strip().lower(),
                ollama_url=env.get('OLLAMA_URL', d.ollama_url).rstrip('/'),
                default_model=env.get('OLLAMA_MODEL', d.default_model).strip(),
                voucher_yen=float(env.get('VOUCHER_YEN', d.voucher_yen)),
                gpu_yen_per_hour=float(env.get('GPU_YEN_PER_HOUR', d.gpu_yen_per_hour)),
                idle_shutdown_minutes=float(env.get('IDLE_SHUTDOWN_MINUTES', d.idle_shutdown_minutes)),
                provider_read_timeout_seconds=float(
                    env.get('PROVIDER_READ_TIMEOUT_SECONDS', d.provider_read_timeout_seconds)
                ),
                task_id=env.get('SAKURA_TASK_ID', ''),
            )
        except ValueError as e:
            raise ConfigError(f'Invalid numeric setting: {e}') from e

    def validate(self) -> None:
        """Fail closed: refuse to run a public gateway without a real API key."""
        if self.allow_no_auth:
            return
        if not self.api_key:
            raise ConfigError(
                'SAKURA_AI_API_KEY (or GATEWAY_API_KEY) is not set. Generate one with `openssl rand -hex 32`. '
                '(Set ALLOW_NO_AUTH=1 only for local development.)'
            )
        if self.api_key in PLACEHOLDER_KEYS:
            raise ConfigError('SAKURA_AI_API_KEY is still a placeholder value; replace it.')
        if len(self.api_key) < MIN_KEY_LENGTH:
            raise ConfigError(f'SAKURA_AI_API_KEY must be at least {MIN_KEY_LENGTH} characters.')


if __name__ == '__main__':
    # Used by start.sh to fail fast, before any model download is billed.
    import sys

    try:
        Settings.from_env().validate()
    except ConfigError as e:
        sys.exit(f'Configuration error: {e}')
