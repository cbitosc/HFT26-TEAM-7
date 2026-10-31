"""Optional Featherless summary using aggregated statistics only."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import requests


def make_summary(stats: dict) -> str:
    key = os.environ.get("FEATHERLESS_API_KEY")
    if not key:
        return ("LLM summary unavailable: set FEATHERLESS_API_KEY and FEATHERLESS_MODEL. "
                f"Aggregates: {json.dumps(stats, sort_keys=True)}")
    endpoint = os.environ.get("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1")
    model = os.environ.get("FEATHERLESS_MODEL", "")
    prompt = (
        "Write a concise, cautious camera-trap summary using only these aggregates. "
        "Mention the share of uncertain predictions and that this is a limited subset, "
        "not a population estimate. Do not infer causation or abundance.\n\n" + json.dumps(stats)
    )
    response = requests.post(
        f"{endpoint.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/summary.json"))
    parser.add_argument("--output", type=Path, default=Path("data/insights.md"))
    args = parser.parse_args()
    args.output.write_text(make_summary(json.loads(args.input.read_text())))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
