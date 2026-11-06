# Guidance for coding and automation agents

This repository contains diagnostics software. Use `README.md`, `docs/LLM_USAGE.md`, and `docs/LLM_INDEX.md` as primary documentation; read `llms.txt` for a short resource index.

## Allowed offline workflows

- Run `python provider_monitor.py --help` and `--list-llm-providers`.
- Run `python -m unittest discover -s tests -v` and `python -m py_compile provider_monitor.py`.
- Run `python provider_monitor.py --all-tests --llm-all-providers --demo --output demo_report.html` to generate simulated data.
- Generate the *public* API/crawler registry using `python scripts/build_llm_index.py`.

## Do not

- Never read, print, leak, commit, or upload `api_keys.env`, `.env`, API credentials, tokens, local private keys, or account-specific generated model indexes.
- Never run live API requests, network scans, or paid model inference without the owner's permission.
- Never claim demo results are real. Do not infer ISP fault from a remote service failure alone.
- Never say SSH banner checks authenticate to a host. Do not add active credential guessing or scanning.
- Do not claim `llms.txt` overrides `robots.txt` or forces AI bots to index a website.

## Source of truth

- `provider_monitor.py:LLM_PRESETS` is the source of truth for built-in API hostnames, env vars, and supported modes.
- `scripts/build_llm_index.py` generates the public `llm_index.json` registry; update bot entries only after checking first-party operator documentation.
- `docs/AI_BOT_INDEX.md` explains bot classes, provenance and deployment caveats.
- `model_index.json` is generated account-specific output, not project source.

Keep Python 3.9 compatible, preserve the zero-required-dependency core, and cover new CLI behavior with offline tests. Avoid changing live endpoints or authentication behavior without verification.
