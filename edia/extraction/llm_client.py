"""
Thin Ollama client for the extraction pipeline.

Determinism is the whole point of this module, so the sampling parameters are set
here and nowhere else: temperature=0 is a hard requirement from the Task 4 spec,
and a fixed seed plus top_p/top_k pinned to greedy is what actually makes an
Ollama run reproducible (temperature alone does not, because the default top_k
still samples from a truncated distribution on ties).

Deliberately no ollama-python dependency -- one requests call against the local
HTTP API keeps the install surface identical to the ingestion module's.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import requests

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "mistral"

# Frozen sampling config. Changing these invalidates every scored extraction run.
DETERMINISTIC_OPTIONS: dict = {
    "temperature": 0.0,
    "top_p": 1.0,
    "top_k": 1,
    "seed": 0,
    "repeat_penalty": 1.0,
    "num_ctx": 8192,
    "num_predict": 2048,
}


class OllamaUnavailable(RuntimeError):
    """Ollama is not running, or the requested model is not pulled."""


class OllamaCallFailed(RuntimeError):
    """The model was reached but the call failed after retries."""


@dataclass
class LLMResponse:
    text: str
    model: str
    latency_s: float
    eval_count: int = 0
    raw: dict = field(default_factory=dict)


class OllamaClient:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        host: str = DEFAULT_HOST,
        timeout: int = 600,
        max_retries: int = 2,
        options: dict | None = None,
        allow_sampling: bool = False,
    ):
        """allow_sampling exists for ONE caller: synthetic dataset generation, which
        needs diversity across the 50 pairs. Extraction must never set it -- the
        default refusal below is what keeps temperature=0 a structural guarantee
        rather than a convention someone can forget."""
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.allow_sampling = allow_sampling
        # copy so a caller tweaking one client can't mutate the module-level frozen dict
        self.options = {**DETERMINISTIC_OPTIONS, **(options or {})}
        if self.options["temperature"] != 0.0 and not allow_sampling:
            raise ValueError(
                "temperature must be 0 for extraction runs (Task 4 requirement). "
                "If you are deliberately sampling (synthetic generation, or an "
                "ablation), pass allow_sampling=True and record temperature and seed "
                "in the output so the run is reproducible."
            )

    # -- availability ---------------------------------------------------------

    def list_models(self) -> list[str]:
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=10)
            r.raise_for_status()
        except requests.RequestException as e:
            raise OllamaUnavailable(
                f"Cannot reach Ollama at {self.host}. Is `ollama serve` running? ({e})"
            ) from e
        return [m["name"] for m in r.json().get("models", [])]

    def ensure_available(self) -> None:
        names = self.list_models()
        # ollama reports "mistral:latest" for a bare "mistral" pull
        if not any(n == self.model or n.split(":")[0] == self.model.split(":")[0] for n in names):
            raise OllamaUnavailable(
                f"Model {self.model!r} is not pulled. Run: ollama pull {self.model}\n"
                f"Available: {', '.join(names) or '(none)'}"
            )

    # -- generation -----------------------------------------------------------

    def chat_json(self, system: str, user: str) -> LLMResponse:
        """Single-turn call with Ollama's JSON mode on.

        JSON mode constrains decoding to valid JSON, which removes the most common
        failure (prose wrapped around the object) but not schema errors -- the
        caller still validates.
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "format": "json",
            "options": self.options,
        }

        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            start = time.time()
            try:
                r = requests.post(
                    f"{self.host}/api/chat", json=payload, timeout=self.timeout
                )
                r.raise_for_status()
                data = r.json()
                return LLMResponse(
                    text=data.get("message", {}).get("content", ""),
                    model=self.model,
                    latency_s=round(time.time() - start, 2),
                    eval_count=data.get("eval_count", 0),
                    raw=data,
                )
            except (requests.RequestException, json.JSONDecodeError) as e:
                last_err = e
                if attempt < self.max_retries:
                    time.sleep(2 * (attempt + 1))

        raise OllamaCallFailed(
            f"{self.model} failed after {self.max_retries + 1} attempts: {last_err}"
        ) from last_err


if __name__ == "__main__":
    import sys

    client = OllamaClient(model=sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL)
    try:
        client.ensure_available()
    except OllamaUnavailable as e:
        print(f"UNAVAILABLE: {e}")
        raise SystemExit(1)
    resp = client.chat_json(
        "You output JSON only.", 'Return {"ok": true} and nothing else.'
    )
    print(f"model={resp.model} latency={resp.latency_s}s -> {resp.text.strip()}")
