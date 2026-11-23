# IARG Assistant — One Pager

## Problem
Users of the IARG dashboard (risk analysts, PMs, engineers) need to understand
how risk scores are computed, when insurance triggers, how to report a Drive
breach, and what each dashboard surface does — without digging through source
code, Confluence, or Slack. Today they context-switch to ChatGPT or ask a
teammate, which breaks flow and leaks product context into third-party chats.

## Goal
Ship an in-product chat tab that answers IARG questions (and general ones)
with quality replies when a user supplies an API key, and still works out of
the box with no setup for a quick demo.

## Users
Anyone opening the IARG dashboard: analysts triaging a scan, PMs demoing to a
customer, engineers onboarding to the codebase.

## Solution (what we built)
A new **Assistant** tab in the dashboard (`/chat`) that talks to a backend
proxy on the Guardian service (`POST /api/guardian/chat`). The proxy routes
to one of two upstream providers:

- **Perplexity Sonar** (primary) — OpenAI-compatible, web-grounded with
  citations. Used when `PERPLEXITY_API_KEY` is set. Default model: `sonar`.
- **LLM7.io** (fallback) — free, no-key public LLM router. Used when the
  Perplexity key is missing, or as a silent fallback for transient 5xx errors.

Routing is controlled by `GUARDIAN_CHAT_PROVIDER` (`auto` by default). A
system prompt primes the model with IARG product context so answers are
grounded in the dashboard the user is already looking at — critical for Sonar,
which otherwise would web-search "IARG" and surface unrelated hits (industrial
asset recovery, a TASE ticker, …).

## Why this shape
- **One UI, swappable upstreams** — frontend never changes when we add,
  rotate, or disable a provider. Guardian is the single egress point.
- **Grounded answers, not just chat** — Sonar's citations make the Assistant
  useful for compliance-adjacent audiences; the system prompt pins the
  product identity so hits like "IARG = Industrial Asset Recovery Group" are
  explicitly ruled out.
- **No regression on no-key demo** — removing the Perplexity key reverts
  cleanly to the free LLM7 fallback.
- **Reuses existing primitives** — Vite proxy, Tailwind design tokens,
  react-query/axios client, Guardian FastAPI router, httpx. No new infra.

## Success criteria
- A user can open `/chat`, send a message, and get a formatted reply in <5s
  on the default model.
- Answers to IARG product questions reference the local product (threshold 70,
  5 risk factors, breach endpoint path), not unrelated web entities.
- `GET /api/guardian/chat/providers` reports `active: "perplexity"` whenever a
  key is set.
- Removing the key and restarting Guardian flips `active` to `"llm7"` with no
  frontend change.
- Markdown in replies renders as formatted text (bold, lists, code, links).
  Sonar citations render as a `Sources:` footer with clickable URLs.

## Explicit non-goals (MVP)
- Conversation persistence (reload clears history).
- Streaming responses (single request/response for simplicity).
- RAG over live Guardian DB (scan results, purchases) — system prompt is
  static product context, not retrieved per-question.
- Auth, per-user rate limits, moderation, prompt-injection scrubbing.

## Risks
- **Key exposure** — `PERPLEXITY_API_KEY` lives in `.env`. Mitigation: no
  log statements include it; CORS limits dashboard origin; the key is never
  echoed in responses.
- **Upstream drift / cost** — Sonar pricing or availability can change.
  Mitigation: `GUARDIAN_CHAT_PROVIDER=llm7` forces the free path; model
  aliases are centralized in `routes.py`.
- **Web-grounding leaking off-topic hits** — Sonar may surface the wrong
  "IARG". Mitigation: strong system prompt + model picker lets users switch
  to a non-web Perplexity reasoning variant if needed.
- **Data leakage** — users may paste secrets into the chatbox. Mitigation:
  disclaimer under the input; nothing from `.env`/DB is ever sent.

## Status
Shipped behind the `Assistant` nav item.

- Frontend: `app/dash/src/pages/Chat.tsx` (model picker populated from
  `/api/guardian/chat/providers`).
- Backend endpoints: `POST /api/guardian/chat`, `GET
  /api/guardian/chat/providers`.
- See [`requirements.md`](./requirements.md), [`design.md`](./design.md),
  [`wireframes.md`](./wireframes.md).
