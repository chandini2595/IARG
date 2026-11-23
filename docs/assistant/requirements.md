# IARG Assistant — Requirements

## 1. Scope

A new tab inside the existing IARG dashboard (`/chat`) that lets a user chat
with an LLM about IARG and general questions. All interaction stays inside the
dashboard; no third-party UI, no sign-up required for the demo path.

Primary upstream: **Perplexity Sonar** (OpenAI-compatible, web-grounded).
Fallback upstream: **LLM7.io** (free, no key).

Out of scope for this iteration: streaming, persistence, auth, RAG on
live dashboard data, file/image upload.

## 2. User stories

| # | As a… | I want to… | So that… |
|---|---|---|---|
| U1 | risk analyst | ask what a given risk component means | I can interpret the score without reading source |
| U2 | PM demoing IARG | ask what each tab does | I don't have to tab out of the demo |
| U3 | engineer onboarding | ask how insurance triggers are decided | I can skip reading `guardian_service.py` end to end |
| U4 | security user | ask how to report a Drive breach | I don't have to find `MVP.md` first |
| U5 | any user | type a general question (not IARG-specific) | the assistant stays useful outside the IARG domain |
| U6 | admin | swap or rotate the LLM provider | I don't have to redeploy or touch frontend code |

## 3. Functional requirements

### F1. Nav + routing
- A new sidebar entry labeled **Assistant** with a chat-bubble icon, placed
  between **Insurance** and **Settings**.
- Clicking it routes to `/chat`.
- Route is reachable via direct URL and survives page refresh.

### F2. Send and receive
- The user types a message and either presses **Enter** or clicks the send
  button to submit.
- **Shift+Enter** inserts a newline.
- During a request, the send button becomes a **Stop** button that aborts the
  in-flight request.
- Replies render as markdown (bold, italics, lists, inline code, code blocks,
  tables, blockquotes, links).
- When the active provider returns citations (Perplexity Sonar), replies end
  with a `Sources:` footer listing the first 5 URLs; links are clickable.

### F3. Model selection
- On page load the frontend calls `GET /api/guardian/chat/providers` and
  renders the model dropdown based on the active provider:
  - **Perplexity (default when key is set)**:
    - `sonar` (default) — web-grounded, fast
    - `sonar-pro` — higher quality, more citations
    - `sonar-reasoning` — step-by-step reasoning
    - `sonar-reasoning-pro` — biggest reasoning model
  - **LLM7 (fallback when no key)**:
    - `mistral-nemo` (default)
    - `gpt-oss` (reasoning)
    - `nemotron` (reasoning)
- Selected model persists for the session (no persistence across reloads).
- The subtitle under the page title reflects the active provider.

### F4. Conversation state
- Messages accumulate in order within one session.
- A trash icon in the header clears the conversation and aborts any in-flight
  request. Disabled when there's nothing to clear.
- On page unload, in-flight requests are aborted.

### F5. Empty state
- When no messages have been sent, the chat area shows a short greeting with 4
  canned IARG prompts the user can click to send directly:
  1. What does the IARG dashboard do?
  2. How is a risk score computed in IARG?
  3. When does IARG trigger insurance automatically?
  4. How can I report a Google Drive breach?

### F6. Error handling
- Upstream 4xx/5xx errors surface as a toast and an inline assistant bubble
  starting with `_Error contacting model_:`.
- Rate-limit errors (HTTP 429) show the suggested retry delay from the
  upstream (`"Model is rate-limited. Retry in Xs."` for LLM7; `"Perplexity
  rate limit exceeded. Try again shortly."` for Sonar).
- Perplexity auth failures (401/403) show a clear error that the API key is
  invalid or missing.
- Aborted requests do not add an error bubble.

### F7. Content safety / data handling
- A disclaimer under the input reads: *"Responses come from a public free
  model and may be inaccurate. Avoid sending sensitive data."*
- The system prompt pins IARG as *this* product (not the "Industrial Asset
  Recovery Group" or TASE ticker) so Sonar's web grounding does not drift.
- No content from `.env`, DB, or other services is ever included in requests.
- The `PERPLEXITY_API_KEY` value is never logged or echoed in responses.

### F8. Backend proxy
- A new endpoint `POST /api/guardian/chat` on the Guardian FastAPI service
  accepts `{ "model": string, "messages": [{"role","content"}, ...] }` and
  returns `{ "model": string, "provider": "perplexity"|"llm7", "content": string }`.
- A companion endpoint `GET /api/guardian/chat/providers` reports the
  configured provider mode, the currently active provider, Perplexity
  availability, and model allow-lists for each provider.
- The endpoint routes to one of two providers:
  - Perplexity: `https://api.perplexity.ai/chat/completions` with Bearer auth.
  - LLM7: `https://api.llm7.io/v1/chat/completions` (no auth).
- Model aliasing is centralized server-side so a stale frontend never breaks
  the API.
- Falls back to `content` from the `reasoning` / `reasoning_content` fields
  when a reasoning model leaves `content` empty.
- Perplexity `citations` (or `search_results`) are appended to the content as
  a `Sources:` footer when present.

### F9. Provider configuration
- Three environment variables control routing:
  - `GUARDIAN_CHAT_PROVIDER`: `auto` (default), `perplexity`, or `llm7`.
  - `PERPLEXITY_API_KEY`: Perplexity key; required for Perplexity routing.
  - `PERPLEXITY_DEFAULT_MODEL`: default model id (defaults to `sonar`).
- In `auto` mode:
  - Routes to Perplexity when the key is set, else LLM7.
  - A transient Perplexity failure (not 401/403/429) silently retries on LLM7
    so the UI stays responsive.
- Explicit `perplexity` mode returns a clear 401 when the key is missing.

## 4. Non-functional requirements

| ID | Requirement |
|---|---|
| N1 | Zero config to demo: with no key set, chat works via LLM7. |
| N2 | One env var to upgrade: setting `PERPLEXITY_API_KEY` is enough to switch providers (plus a `docker compose up -d guardian`). |
| N3 | No new runtime services; reuses the existing Guardian container. |
| N4 | First reply round-trip ≤ 5s at p50 on the default Sonar model under normal upstream conditions. |
| N5 | Page is keyboard-usable: focus moves back to the input after each reply. |
| N6 | Dark theme consistent with the rest of the dashboard (Tailwind + `card`, `btn-primary`, `btn-secondary` design tokens). |
| N7 | Scrolls to the latest message automatically. |
| N8 | No PII, secrets, or API keys are logged by the proxy. |
| N9 | Removing the Perplexity key and restarting Guardian cleanly reverts to LLM7 without a frontend change. |

## 5. Acceptance checks

- [ ] Open `http://localhost:3000/chat` from a cold Vite boot — Assistant tab shows a greeting and 4 chips.
- [ ] `GET /api/guardian/chat/providers` reports `active: "perplexity"` when the key is set.
- [ ] Click any chip — a request fires, a typing indicator renders, a markdown-formatted reply appears with a `Sources:` footer.
- [ ] Type a question with `**bold**` and `- list` in the response — formatting renders, not raw asterisks.
- [ ] Ask "What is IARG?" — the answer references *this* product (threshold 70, risk factors, dashboard), not the Industrial Asset Recovery Group or TASE ticker.
- [ ] Switch the model dropdown; next reply's `provider` field in `/api/guardian/chat` body matches the switch, and the model id reflects the choice.
- [ ] Press Stop mid-request — no error bubble, UI returns to idle.
- [ ] Click trash — history clears; chip empty state returns.
- [ ] Hit the backend with an invalid Perplexity model name — gets 200 with the Perplexity default (silent coercion), not a 500.
- [ ] Unset `PERPLEXITY_API_KEY` and restart Guardian — `/providers` reports `active: "llm7"`, model picker shows the LLM7 models, chat still works.
- [ ] Set `GUARDIAN_CHAT_PROVIDER=perplexity` with no key — the backend returns 401 with a clear error message (not a 500).
