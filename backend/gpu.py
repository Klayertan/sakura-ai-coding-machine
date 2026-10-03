"""GPU telemetry via nvidia-smi (present in the container through the NVIDIA runtime)."""
import subprocess
from typing import Optional

_QUERY = 'name,memory.used,memory.total,utilization.gpu'


def parse_nvidia_smi(output: str) -> Optional[dict]:
    lines = [l for l in output.splitlines() if l.strip()]
    if not lines:
        return None
    parts = [p.strip() for p in lines[0].split(',')]
    if len(parts) != 4:
        return None
    try:
        return {
            'name': parts[0],
            'memory_used_mb': int(parts[1]),
            'memory_total_mb': int(parts[2]),
            'utilization_percent': int(parts[3]),
        }
    except ValueError:
        return None


def gpu_stats() -> Optional[dict]:
    try:
        out = subprocess.run(
            ['nvidia-smi', f'--query-gpu={_QUERY}', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_nvidia_smi(out)
