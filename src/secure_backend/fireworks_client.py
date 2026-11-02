"""Fireworks chat client. Reads FIREWORKS_API_KEY from the environment or the repo's .env."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://api.fireworks.ai/inference/v1/chat/completions"
REPO_ROOT = Path(__file__).resolve().parents[2]

# USD per million tokens (input, output). Check against fireworks.ai/pricing before final numbers;
# prices.json at the repo root overrides these.
DEFAULT_PRICES = {
    "accounts/fireworks/models/deepseek-v4p1-flash-1017": (0.30, 1.20),
    "accounts/fireworks/models/nemotron-nano-3-30b-a3b": (0.10, 0.40),
}


def _load_key() -> str:
    key = os.environ.get("FIREWORKS_API_KEY")
    if key:
        return key
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("FIREWORKS_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("FIREWORKS_API_KEY not set (environment or .env)")


def load_prices() -> dict:
    prices = dict(DEFAULT_PRICES)
    override = REPO_ROOT / "prices.json"
    if override.exists():
        prices.update({k: tuple(v) for k, v in json.loads(override.read_text()).items()})
    return prices


class FireworksClient:
    def __init__(self, model: str, temperature: float = 0.4, max_tokens: int = 8192,
                 price_model: str | None = None, retries: int = 5, reasoning_effort: str | None = "none"):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.retries = retries
        # Every arm runs without a thinking phase: with it, DeepSeek spent the whole token budget
        # reasoning and returned no code on 18 of 64 training runs.
        self.reasoning_effort = reasoning_effort
        self.key = _load_key()
        # A tuned deployment is billed like its base model.
        self.price_in, self.price_out = load_prices().get(price_model or model, (0.0, 0.0))

    def cost(self, tokens_in: int, tokens_out: int) -> float:
        return (tokens_in * self.price_in + tokens_out * self.price_out) / 1e6

    def generate(self, messages: list) -> dict:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.reasoning_effort is not None:
            payload["reasoning_effort"] = self.reasoning_effort
        body = json.dumps(payload).encode()
        delay = 2.0
        for attempt in range(self.retries + 1):
            req = urllib.request.Request(API_URL, data=body, headers={
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
            })
            start = time.monotonic()
            try:
                with urllib.request.urlopen(req, timeout=300) as resp:
                    data = json.loads(resp.read())
                break
            except urllib.error.HTTPError as e:
                if e.code not in (429, 500, 502, 503, 504) or attempt == self.retries:
                    raise RuntimeError(f"Fireworks {e.code}: {e.read()[:500]!r}") from None
            except (urllib.error.URLError, TimeoutError):
                if attempt == self.retries:
                    raise
            time.sleep(delay)
            delay = min(delay * 2, 60)
        latency = time.monotonic() - start
        usage = data.get("usage") or {}
        return {
            "text": data["choices"][0]["message"].get("content") or "",
            "tokens_in": int(usage.get("prompt_tokens", 0)),
            "tokens_out": int(usage.get("completion_tokens", 0)),
            "latency_s": round(latency, 3),
        }
