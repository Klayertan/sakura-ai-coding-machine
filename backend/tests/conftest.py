import sys
from pathlib import Path

# The container runs with backend/ as its working directory; mirror that here.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
