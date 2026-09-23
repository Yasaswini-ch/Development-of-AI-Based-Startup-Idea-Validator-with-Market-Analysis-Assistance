"""Milestone 4 / Track F - live Render deployment/regression check.

Unlike smoke_test.py (local Python-logic checks, no network), this hits
the actual deployed URLs from render.yaml over HTTPS - run this after any
deploy to confirm the live services are actually up and wired together
correctly, not just that the local test suite passes.

Usage (stdlib only, no extra install - just internet access; no Render
dashboard login required, these are public URLs):

    python backend/scripts/render_deployment_check.py
    python backend/scripts/render_deployment_check.py --full   # also runs a
                                                                 # real /validate
                                                                 # request - see
                                                                 # the --full
                                                                 # warning below

--full makes one real POST /validate call, which runs the entire live
pipeline against real Groq/Tavily/Gemini API keys on the deployed backend -
real API quota, ~5-30s. Safe to run occasionally after a deploy; don't
script it into a tight loop or CI cron.
"""

import argparse
import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# From render.yaml - update here if the deployed URLs ever change.
BACKEND_URL = "https://startup-validator-backend-pruu.onrender.com"
FRONTEND_URL = "https://startup-validator-frontend-5qcr.onrender.com"

_TIMEOUT_SECONDS = 15


def _get(url: str) -> tuple[int, str]:
    try:
        with urlopen(Request(url), timeout=_TIMEOUT_SECONDS) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except URLError as exc:
        return 0, str(exc.reason)


def _post_json(url: str, payload: dict) -> tuple[int, str]:
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        # /validate can legitimately take a while on a real pipeline run -
        # a free-tier Render instance waking from sleep adds to that, so
        # this uses its own longer timeout rather than _TIMEOUT_SECONDS.
        with urlopen(req, timeout=90) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except URLError as exc:
        return 0, str(exc.reason)


def _check(name: str, condition: bool, detail: str) -> bool:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}{' - ' + detail if detail else ''}")
    return condition


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--full",
        action="store_true",
        help="Also run a real end-to-end /validate request (uses real API quota).",
    )
    args = parser.parse_args()

    all_passed = True
    start = time.time()

    status, body = _get(f"{BACKEND_URL}/health")
    all_passed &= _check("Backend /health responds 200", status == 200, f"got {status}: {body[:200]}")
    if status == 200:
        try:
            all_passed &= _check("Backend /health has expected shape", json.loads(body).get("status") == "ok", body[:200])
        except json.JSONDecodeError:
            all_passed &= _check("Backend /health returns valid JSON", False, body[:200])

    status, body = _get(f"{BACKEND_URL}/")
    all_passed &= _check("Backend root / responds 200", status == 200, f"got {status}")

    status, body = _get(FRONTEND_URL)
    all_passed &= _check("Frontend responds 200", status == 200, f"got {status}")
    all_passed &= _check(
        "Frontend serves the SPA shell",
        '<div id="root">' in body or "id=\"root\"" in body,
        "no #root mount point found in HTML" if status == 200 else "skipped, page did not load",
    )

    if args.full:
        print("\n--full: running a real end-to-end /validate request (real API quota, may take up to ~60s)...")
        status, body = _post_json(
            f"{BACKEND_URL}/validate",
            {
                "idea": "A subscription meal-kit service for busy professionals",
                "targetCustomer": "Busy working professionals",
                "problem": "No time to plan and cook healthy meals",
            },
        )
        ok = status == 200
        all_passed &= _check("Live /validate completes", ok, f"got {status}" + ("" if ok else f": {body[:300]}"))
        if ok:
            try:
                data = json.loads(body)
                expected_keys = {"summary", "results", "confidence", "marketOpportunity", "swot", "mvp", "gtm", "errors"}
                missing = expected_keys - data.keys()
                all_passed &= _check("Live /validate response has expected keys", not missing, f"missing: {missing}")
                errors = data.get("errors") or {}
                all_passed &= _check(
                    "Live /validate ran with no section errors", not any(errors.values()), f"errors: {errors}"
                )
            except json.JSONDecodeError:
                all_passed &= _check("Live /validate returns valid JSON", False, body[:300])

    elapsed = round(time.time() - start, 1)
    print(f"\n{'All checks passed' if all_passed else 'SOME CHECKS FAILED'} ({elapsed}s)")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
