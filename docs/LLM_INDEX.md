# LLM provider index

This project has **two kinds of indexes**:

1. `llm_index.json` is the **public, static registry** of supported LLM API providers and documented AI crawlers. It contains no credentials and no account-specific model IDs.
2. `model_index.json` is an **optional, locally generated snapshot** of model identifiers returned from your own API accounts. It is deliberately excluded from Git.

For an LLM-readable documentation map for coding assistants, see [`../llms.txt`](../llms.txt). For website indexing bots, see [`AI_BOT_INDEX.md`](AI_BOT_INDEX.md).

## Built-in LLM APIs

| Provider | API base URL | API key variable | `models` | `chat` | `responses` |
|---|---|---|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `OPENAI_API_KEY` | Yes | Yes | Yes |
| Anthropic Claude | `https://api.anthropic.com/v1` | `ANTHROPIC_API_KEY` | Yes | Yes — native Messages API | No |
| Kimi (Moonshot) | `https://api.moonshot.ai/v1` | `KIMI_API_KEY` (also `MOONSHOT_API_KEY`) | Yes | Yes | No |
| Mistral | `https://api.mistral.ai/v1` | `MISTRAL_API_KEY` | Yes | Yes | No |

"No" means **this monitor does not implement that mode for the preset**; it does not imply that a provider has no alternative API or never will.

## List the providers without an API key

```bash
python provider_monitor.py --list-llm-providers
```

## Create or refresh the public static index

```bash
python scripts/build_llm_index.py
```

This generates `llm_index.json` from the monitor's built-in API presets and the documented crawler directory. It does **not** connect to the internet or expose any user accounts.

## Create a private model-ID index from your provider accounts

First, create `api_keys.env` from `api_keys.env.example` and insert your actual credentials locally. Then run:

```bash
python scripts/fetch_model_index.py --all-providers --env-file api_keys.env --output model_index.json
```

To query one provider:

```bash
python scripts/fetch_model_index.py --provider mistral --env-file api_keys.env
```

The model indexer performs authenticated `GET /models` requests only. It never invokes generation, saves only model IDs and display names, and reports failed providers separately. **Some APIs paginate; only the first page is indexed when `partial` is true.** This is not a full capabilities or price catalog. Never commit the generated file without reviewing which account-specific model IDs you wish to disclose.

## Further reading

- [LLM usage guide](LLM_USAGE.md)
- [AI crawler/bot index](AI_BOT_INDEX.md)
- [Public `llms.txt` overview](../llms.txt)
