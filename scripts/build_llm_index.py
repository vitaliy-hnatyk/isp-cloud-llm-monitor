#!/usr/bin/env python3
"""Build public, credential-free LLM provider and AI bot indexes from verified metadata."""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from provider_monitor import LLM_PRESETS  # noqa: E402

# Descriptions and user-agent identifiers from official operator documentation.
BOTS = [
    {"agent": "OAI-SearchBot", "operator": "OpenAI", "role": "search-discovery", "source": "https://developers.openai.com/api/docs/bots"},
    {"agent": "GPTBot", "operator": "OpenAI", "role": "training-crawler", "source": "https://developers.openai.com/api/docs/bots"},
    {"agent": "ChatGPT-User", "operator": "OpenAI", "role": "user-initiated-fetch", "source": "https://developers.openai.com/api/docs/bots"},
    {"agent": "Claude-SearchBot", "operator": "Anthropic", "role": "search-discovery", "source": "https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler"},
    {"agent": "ClaudeBot", "operator": "Anthropic", "role": "training-crawler", "source": "https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler"},
    {"agent": "Claude-User", "operator": "Anthropic", "role": "user-initiated-fetch", "source": "https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler"},
    {"agent": "Google-Extended", "operator": "Google", "role": "usage-control-token-not-separate-http-user-agent", "source": "https://developers.google.com/crawling/docs/crawlers-fetchers/google-common-crawlers"},
]

def build():
    providers = []
    for slug, (label, base, key_env) in LLM_PRESETS.items():
        providers.append({
            "id": slug, "label": label, "api_base_url": base,
            "api_key_environment_variable": key_env,
            "monitor_modes": ["models", "chat", "responses"] if slug == "openai" else ["models", "chat"],
            "models_route": "/models",
            "inference_route": "/messages" if slug == "anthropic" else "/chat/completions",
            "model_ids": "Discover via authenticated /models; not hardcoded",
        })
    return {
        "schema_version": "1.0", "last_reviewed": "2026-11-06",
        "description": "Public project capabilities and crawler identities. No credentials or live models are included.",
        "providers": providers, "ai_crawlers": BOTS,
        "notes": [
            "Provider APIs and website crawling user agents are separate concepts.",
            "Google-Extended is a robots.txt product token, not a distinct HTTP user-agent.",
            "No verified public crawler token is claimed for Kimi/Mistral here.",
            "Index is static metadata, not a live uptime or model inventory.",
        ],
    }

if __name__ == "__main__":
    path = ROOT / "llm_index.json"
    path.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {path}")
