# AI crawler and LLM-bot index

**AI crawler user agents are not the same thing as model APIs.** You can call OpenAI, Anthropic, Kimi, and Mistral APIs to test uptime without letting a bot crawl your website. Conversely, a website crawler may read your documentation without possessing your API key.

The bot identities below are based on **operator-published documentation**. Names and behavior can change; verify the official sources before changing production robots policy.

| Operator | robots.txt user-agent/token | Main purpose | Official documentation |
|---|---|---|---|
| OpenAI | `OAI-SearchBot` | Discovery for ChatGPT search | [OpenAI crawlers](https://developers.openai.com/api/docs/bots) |
| OpenAI | `GPTBot` | Training crawler | [OpenAI crawlers](https://developers.openai.com/api/docs/bots) |
| OpenAI | `ChatGPT-User` | Fetches content for user-requested interactions | [OpenAI crawlers](https://developers.openai.com/api/docs/bots) |
| Anthropic | `Claude-SearchBot` | Search result discovery | [Anthropic crawler guidance](https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler) |
| Anthropic | `ClaudeBot` | Training crawler | [Anthropic crawler guidance](https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler) |
| Anthropic | `Claude-User` | User-initiated content retrieval | [Anthropic crawler guidance](https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler) |
| Google | `Google-Extended` | Robots product token affecting Gemini training/grounding, not a distinct HTTP bot | [Google common crawlers](https://developers.google.com/crawling/docs/crawlers-fetchers/google-common-crawlers) |

For Kimi and Mistral, this repository does **not** claim any verified official crawler user-agent token. The API providers are nevertheless listed in [`LLM_INDEX.md`](LLM_INDEX.md).

## The three different indexing mechanisms

- **`llms.txt`**: a voluntary, Markdown resource map that AI agents *may* read. This is a community proposal, not a binding crawler policy and not a guarantee of discovery or citations. See [llmstxt.org](https://llmstxt.org/).
- **`robots.txt`**: server-root instructions that compliant web crawlers interpret. The included `robots.txt` file is a **sample policy** allowing search crawlers and opting out of recognized training crawlers by default. Adapt to your legal and publishing goals.
- **`llm_index.json`**: this repository's machine-readable inventory of its LLM API presets and selected publicly documented crawler tokens. It is not a universal directory of AI bots.

## Publishing on GitHub and on a website

On a **GitHub repository**, `llms.txt`, `robots.txt`, and Markdown documentation are repository files. Uploading them to GitHub does **not** modify GitHub's own domain-wide `robots.txt` rules. To publish a crawler policy for a website you control, serve `robots.txt` from the site's origin root (`https://your-domain.example/robots.txt`). A GitHub Pages project site at `/owner/repo/` usually does not control the hostname root; use a custom domain you control for root policy.

Publish `llms.txt` where you want a capable agent to find the index (typically `https://your-domain.example/llms.txt`), check links after deployment, and optionally expose it from your site navigation. This repository uses **relative Markdown links** so it works when browsing the files locally; update them to absolute published URLs if your consumer requires them.

`robots.txt` is **not authentication**. It cannot protect private APIs, credentials, or admin pages. A bot can spoof a User-Agent header; verify claimed bots using their operators' published IP ranges or documented verification instructions.

## Example robots policy

See [`../robots.txt`](../robots.txt). It allows known search/retrieval agents, and opts out of GPTBot, ClaudeBot, and Google-Extended by default. Blocking Google-Extended can also affect Gemini grounding; review whether that is your intent. User-initiated retrieval may not always be governed by robots rules (for example, OpenAI's ChatGPT-User documentation notes this).

**Review date:** November 6, 2026. Bot identities and capabilities are subject to change.
