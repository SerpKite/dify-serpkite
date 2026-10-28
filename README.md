# SerpKite for Dify

Real-time Google results, webpages, cited answers and AI assistant answers for Dify agents and workflows, from [SerpKite](https://serpkite.com).

Source: https://github.com/SerpKite/dify-serpkite
Contact: support@serpkite.com

## Setup

1. Install **SerpKite** from the Dify Marketplace (or upload the `.difypkg` from a [release](https://github.com/SerpKite/dify-serpkite/releases) via **Plugins → Install from local package**).
2. Create a SerpKite account at https://app.serpkite.com and an API key (new accounts get free credits).
3. Authorize the SerpKite provider with the full `skt_live_...` key. The check calls `GET /v1/account`, which is free.
4. Add the tools you need to an agent, a chatflow or a workflow.

## Tools

| Group | Tools |
| --- | --- |
| Google search | Web Search, News Search, Image Search, Video Search, Shopping Search, Scholar Search, Patent Search, Autocomplete |
| Places | Maps Search, Place Details |
| Pages and sites | Fetch Webpage, Extract Pages (highlights, AI summary, JSON by schema), Map a Site, Start Site Crawl + Get Crawl Result |
| AI answers | Answer with Citations, Start Deep Research + Get Research Result |
| AI assistants | Ask ChatGPT, Ask Gemini, Ask Copilot Search, Ask Google AI Mode, Ask Brave |

**AI assistants** ask ChatGPT, Gemini, Microsoft Copilot Search, Google AI Mode or Brave Search's AI answer as a logged-out visitor and return the answer with the sources it cited. `Track` takes brands or domains and reports whether the answer names or cites each one. Answers usually take 1–10 s (Brave), 5–30 s (Gemini), 10–30 s (ChatGPT), 15–40 s (Copilot Search) and 5–45 s (AI Mode). If an answer is still being finished when the request ends, the tool says so: run it again with the same prompt within 10 minutes to receive it.

**Crawls and research** run in the background: the start tool returns a task ID, and the result tool waits up to `Wait (seconds)` (default 60) for it to finish, then returns the pages or the cited report, or the current progress.

## Outputs

Search, Place, Webpage and assistant tools have an **Output** setting: `markdown` (default) returns readable Markdown for a model, `json` returns the full JSON response for workflow variables plus a short Markdown summary. Web Search and News Search default to `json` (as in 0.0.x). The other tools always return both JSON and Markdown. API errors stop the tool with SerpKite's error message.

## Billing

Each tool call is billed like the API request it makes; see https://serpkite.com/pricing. Failed and empty requests are not billed, and getting crawl or research results is free.

## Connection requirements

The plugin connects only to `https://api.serpkite.com` (port 443); the plugin daemon needs outbound HTTPS to that host. Credential checks time out after 30 seconds, searches after 90 seconds, and AI assistants, answers and extraction after 150 seconds.

## Privacy

See [PRIVACY.md](PRIVACY.md).

## Development

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt pytest pyyaml
.venv/bin/python -m pytest tests
dify plugin package .   # official Dify plugin CLI
```

Tests mock HTTP and use no credits.
