#!/usr/bin/env python3
"""Fetch model IDs from authenticated LLM /models endpoints; do not persist secrets."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from provider_monitor import LLM_PRESETS, LLM_HTTP_OPENER, load_env_file  # noqa: E402


def fetch_one(provider: str, timeout: float) -> dict:
    label, base_url, key_env = LLM_PRESETS[provider]
    key = os.environ.get(key_env, "").strip()
    if provider == "kimi" and not key:
        key = os.environ.get("MOONSHOT_API_KEY", "").strip()
    if not key:
        raise ValueError(f"Missing {key_env} for {provider}")
    headers = {"Accept": "application/json", "User-Agent": "ProviderMonitor-ModelIndexer/1.0"}
    if provider == "anthropic":
        headers.update({"x-api-key": key, "anthropic-version": "2026-10-21"})
        workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID", "").strip()
        if workspace_id:
            headers["anthropic-workspace-id"] = workspace_id
    else:
        headers["Authorization"] = f"Bearer {key}"
    url = base_url.rstrip("/") + "/models"
    try:
        with LLM_HTTP_OPENER.open(Request(url, headers=headers, method="GET"), timeout=timeout) as response:
            status = response.status
            raw = response.read(2_000_000)
    except HTTPError as exc:
        # Never print response bodies, which may contain confidential information.
        raise ValueError(f"{provider} returned HTTP {exc.code}") from None
    except URLError as exc:
        raise ValueError(f"{provider} request failed: {type(exc.reason).__name__}") from None
    if status != 200:
        raise ValueError(f"{provider} returned HTTP {status}")
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise ValueError(f"{provider} returned invalid JSON") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError(f"{provider} returned no data list")
    # Deliberately store only model identifiers and human-readable names.
    models = []
    for row in payload["data"]:
        if isinstance(row, dict) and isinstance(row.get("id"), str):
            models.append({"id": row["id"], "name": str(row.get("display_name") or row["id"])})
    return {"provider": provider, "endpoint": base_url, "model_count": len(models),
            "models": models, "partial": bool(payload.get("has_more", False))}


def main(argv=None):
    parser = argparse.ArgumentParser(description="List LLM model IDs your account can access (no inference calls).")
    parser.add_argument("--provider", action="append", choices=list(LLM_PRESETS), default=[], help="Provider; repeat this flag")
    parser.add_argument("--all-providers", action="store_true", help="Query all four configured providers")
    parser.add_argument("--env-file", default="api_keys.env", help="Local secrets file (ignored by git)")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--output", default="model_index.json", help="Local output JSON, ignored by git")
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    chosen = list(dict.fromkeys((list(LLM_PRESETS) if args.all_providers else []) + args.provider))
    if not chosen:
        parser.error("Choose --provider NAME or --all-providers")
    if args.env_file and Path(args.env_file).is_file():
        load_env_file(args.env_file)
    records, errors = [], []
    for provider in chosen:
        try:
            record = fetch_one(provider, args.timeout)
        except (ValueError, OSError) as exc:
            errors.append({"provider": provider, "error": str(exc)})
            print(f"{provider}: failed ({exc})")
        else:
            print(f"{provider}: {record['model_count']} model IDs" + (" (first page only)" if record['partial'] else ""))
            records.append(record)
    result = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
              "note": "Account-specific snapshot; may be partial or change with access rights; no API keys or generated text stored.",
              "providers": records, "errors": errors}
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {out}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
