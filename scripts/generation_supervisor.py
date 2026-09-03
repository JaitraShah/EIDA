"""
Keep synthetic generation running until the whole plan is on disk.

The 2040-pair run is a multi-day job on CPU (~165 s/pair measured), so the thing
that actually kills it is not a bug -- it is the process dying: Ollama restarting,
a laptop sleeping, a session ending. `generate_synthetic.py` is already resumable
(skip-if-exists + append-only manifest), so the fix is just to keep relaunching it.

This supervisor:
  * waits for Ollama to answer before each attempt,
  * runs one `generate_synthetic.py` pass,
  * backs off exponentially only when a pass makes **no progress** (a real fault),
    and resets the backoff as soon as pairs are being produced again,
  * stops when the plan is complete, or on --max-hours / Ctrl-C.

    python scripts/generation_supervisor.py                 # until the plan is done
    python scripts/generation_supervisor.py --max-hours 8   # overnight slice
    python scripts/generation_supervisor.py --target 500    # stop early at N pairs
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests

from edia.benchmark.generate import PAIRS_DIR
from edia.benchmark.topics import pair_plan
from edia.extraction.llm_client import DEFAULT_HOST

LOG = Path("outputs/generation_supervisor.log")
MIN_BACKOFF = 30
MAX_BACKOFF = 900


def generated_count() -> int:
    return len(list(PAIRS_DIR.glob("SYN_*.json"))) if PAIRS_DIR.exists() else 0


def log(msg: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def ollama_ready(host: str, model: str, timeout: int = 10) -> bool:
    try:
        r = requests.get(f"{host}/api/tags", timeout=timeout)
        r.raise_for_status()
        names = [m["name"] for m in r.json().get("models", [])]
    except requests.RequestException:
        return False
    return any(n.split(":")[0] == model.split(":")[0] for n in names)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="mistral")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--target", type=int, default=None,
                    help="stop at N generated pairs (default: the whole plan)")
    ap.add_argument("--max-hours", type=float, default=None)
    ap.add_argument("--batch", type=int, default=25,
                    help="pairs per generate_synthetic.py pass (a smaller batch "
                         "checkpoints the supervisor's own view more often)")
    args = ap.parse_args(argv)

    target = args.target or len(pair_plan())
    deadline = (time.time() + args.max_hours * 3600) if args.max_hours else None
    backoff = MIN_BACKOFF
    started = time.time()
    start_count = generated_count()

    log(f"supervisor start: {start_count}/{target} pairs on disk"
        + (f", max {args.max_hours}h" if args.max_hours else ""))

    while True:
        have = generated_count()
        if have >= target:
            log(f"COMPLETE: {have}/{target} pairs")
            return 0
        if deadline and time.time() > deadline:
            log(f"time budget reached: {have}/{target} pairs")
            return 0

        if not ollama_ready(args.host, args.model):
            log(f"Ollama not ready at {args.host} -- waiting {backoff}s")
            time.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)
            continue

        before = have
        log(f"pass start at {before}/{target}")
        try:
            subprocess.run(
                [sys.executable, "scripts/generate_synthetic.py",
                 "--model", args.model, "--limit", str(args.batch)],
                check=False,
            )
        except KeyboardInterrupt:
            log("interrupted by user")
            return 130

        after = generated_count()
        made = after - before
        elapsed = time.time() - started
        rate = (after - start_count) / elapsed if elapsed else 0
        eta = timedelta(seconds=int((target - after) / rate)) if rate > 0 else "unknown"
        log(f"pass made {made} pair(s); {after}/{target}; ETA {eta}")

        if made == 0:
            log(f"no progress -- backing off {backoff}s")
            time.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)
        else:
            backoff = MIN_BACKOFF


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        log("supervisor stopped")
        raise SystemExit(130)
