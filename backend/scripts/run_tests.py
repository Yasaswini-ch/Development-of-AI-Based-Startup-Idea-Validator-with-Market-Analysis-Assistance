"""Run the backend test suite without real API keys.

    python scripts/run_tests.py            # whole suite
    python scripts/run_tests.py test_auth  # one module (pass any unittest arguments)

main.py (and litellm) normally load backend/.env on import, which put real Groq and
Gemini keys into the process, so any test reaching an LLM step made real calls and spent
the free quota. This sets AFFINITY_SKIP_DOTENV=1 and LITELLM_MODE=PRODUCTION first, so the suite runs keyless
like CI does. Keys exported in your own shell are removed for the run as well.
"""

import os
import subprocess
import sys
from pathlib import Path

backend = Path(__file__).resolve().parents[1]
# litellm also calls load_dotenv() on import unless LITELLM_MODE is PRODUCTION, and
# backend/.venv sits inside backend/, so it finds backend/.env on its own.
env = {**os.environ, "AFFINITY_SKIP_DOTENV": "1", "LITELLM_MODE": "PRODUCTION"}
for key in ("GROQ_API_KEY", "GEMINI_API_KEY", "TAVILY_API_KEY", "SENDGRID_API_KEY"):
    env.pop(key, None)  # keep a shell-exported key from leaking into tests too

args = sys.argv[1:] or ["discover", "-s", "tests"]
sys.exit(subprocess.call([sys.executable, "-m", "unittest", *args], cwd=backend, env=env))
