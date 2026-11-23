# IARG Assistant — Design & Implementation

## 1. Architecture at a glance

```
+---------------------+        +----------------------+        +----------------+
|   Dashboard (Vite)  |        |   Guardian (FastAPI) |   -->  |  Perplexity    |
|   React / /chat     |  HTTP  |  POST /chat          |        |  /chat/        |
|   src/pages/Chat.tsx| -----> |  GET  /chat/providers|  OR    |  completions   |
+---------------------+ (JSON) |                      |        +----------------+
         ^                     |   Provider router    |   -->  +----------------+
         | Markdown render     |   + citation footer  |        |   LLM7.io      |
         |                     +----------+-----------+        |   fallback     |
         +--------------------------------+                    +----------------+
```

- Frontend never talks to an LLM provider directly. Everything goes through
  the Guardian proxy over the existing Vite dev-server rule
  (`/api/guardian` → `http://localhost:8003`).
- Guardian is the only component with egress to any LLM — easier to swap
  providers, rotate keys, sanitize prompts, or add logging later.
- `GET /chat/providers` lets the frontend render the correct model picker
  without hard-coding which upstream is active.

## 2. Why not call the LLM directly from the browser?

- The `PERPLEXITY_API_KEY` must never ship to the browser.
- Public free LLM gateways (Pollinations, HackClub, etc.) started enforcing
  Turnstile / origin checks on browser requests. Pollinations now returns
  `403 Missing Turnstile token` and later `402 FREE_LIMIT` with 1 reply /
  45 seconds / IP. Running through our FastAPI service is treated as a normal
  server-to-server call — no Turnstile, higher throughput.
- Keeps provider churn invisible to the frontend. We swapped Pollinations →
  LLM7 in a single file, then added Perplexity alongside LLM7 without
  touching the dashboard shell.

## 3. Frontend design (`app/dash`)

### 3.1 Routing & nav

- `App.tsx` adds `<Route path="/chat" element={<Chat />} />`.
- `components/Layout.tsx` adds a new nav entry between Insurance and Settings
  with an inline SVG chat-bubble icon.
- Page shell matches other pages: `p-6 min-h-screen bg-gray-950 text-gray-100`.

### 3.2 Page structure (`pages/Chat.tsx`)

```
Chat
├─ Header (title, provider-aware subtitle, Model <select>, Clear button)
└─ Card (flex column, h = calc(100vh - 10rem))
   ├─ Scroll area
   │   ├─ EmptyState (bot icon + 4 chip prompts) — when no messages
   │   └─ MessageBubble[] + TypingBubble (while loading)
   └─ Form
       ├─ <textarea> (Enter = send, Shift+Enter = newline)
       ├─ Send | Stop button
       └─ Disclaimer
```

### 3.3 State

- `messages: UiMessage[]` — in-memory conversation (role/content/id/ts).
- `input: string` — textarea buffer.
- `isLoading: boolean` — disables input, swaps send→stop, renders typing bubble.
- `abortRef: AbortController` — unmount and manual stop both cancel in-flight.
- `provider: 'perplexity' | 'llm7' | null` — set from `/providers` probe.
- `modelOptions: ModelOption[]` + `model: string` — swapped by provider.

The system prompt is prepended on every outgoing request but filtered out of
`visibleMessages` so it never renders.

### 3.4 Provider probe

On mount, `Chat.tsx` calls `GET /api/guardian/chat/providers`:

```ts
useEffect(() => {
  guardianApi.get('/api/guardian/chat/providers').then((res) => {
    const active = res?.data?.active
    if (active === 'perplexity') {
      setProvider('perplexity')
      setModelOptions(PERPLEXITY_MODELS)
      setModel(PERPLEXITY_MODELS[0].value) // 'sonar'
    } else {
      setProvider('llm7')
      setModelOptions(LLM7_MODELS)
      setModel(LLM7_MODELS[0].value)        // 'mistral-nemo'
    }
  })
}, [])
```

The subtitle changes to reflect the active provider ("Chatbot powered by
Perplexity Sonar (web-grounded answers with citations)." vs. "Free chatbot
powered by a public LLM endpoint. No API key required.").

### 3.5 System prompt

The system prompt is a static block that:

- Declares identity: *IARG = Intangible-Asset Risk Guardian* — explicitly not
  the Industrial Asset Recovery Group or any ticker.
- Lists services, risk-score factors, insurance thresholds, breach endpoint,
  and dashboard tabs so Sonar can answer from product context first.
- Instructs the model to prefer product context and use web only for external
  facts, and to keep the backend-appended `Sources:` footer intact.

### 3.6 Markdown rendering

- `react-markdown` + `remark-gfm` render assistant messages. User messages
  stay as `whitespace-pre-wrap` so a `**` typed by the user isn't surprise-
  interpreted as bold.
- Markdown components are themed to the dashboard: `strong` → `text-white
  font-semibold`, code → `bg-gray-800 text-primary-200`, links →
  `text-primary-300`, tables bordered with `primary-500/20`, etc.

### 3.7 UX details

- `requestAnimationFrame(() => textarea.focus())` after each reply keeps the
  conversation keyboard-driven.
- Auto-scroll uses `scrollTop = scrollHeight` on message count change.
- Stop button is wired to `abortRef.current.abort()`; the catch branch
  ignores `AbortError`/`CanceledError` so cancellation is silent.
- Rate-limit response (HTTP 429) is surfaced via `err.response.data.detail`.

## 4. Backend design (`app/guardian`)

### 4.1 Endpoints

File: `src/api/routes.py`

```python
POST /api/guardian/chat
Body:    { "model": "<alias>", "messages": [{"role": "...", "content": "..."}]}
Returns: { "model": "<real id>", "provider": "perplexity"|"llm7", "content": "..." }

GET  /api/guardian/chat/providers
Returns: {
  "configured": "auto"|"perplexity"|"llm7",
  "active": "perplexity"|"llm7",
  "perplexity_available": bool,
  "models": { "perplexity": [...], "llm7": [...] }
}
```

Pydantic:

```python
class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(..., min_length=1)

class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., min_length=1, max_length=50)
    model: str = "sonar"

class ChatResponse(BaseModel):
    model: str
    provider: str
    content: str
```

### 4.2 Provider selection

```python
def _resolve_provider(model_alias: str) -> str:
    cfg = settings.guardian_chat_provider.lower()
    has_pplx = bool(settings.perplexity_api_key.strip())

    if cfg == "perplexity":           return "perplexity"
    if cfg == "llm7":                 return "llm7"
    if model_alias in PERPLEXITY_ALIASES: return "perplexity" if has_pplx else "llm7"
    if model_alias in LLM7_ALIASES:       return "llm7"
    return "perplexity" if has_pplx else "llm7"
```

- `auto` mode (default) routes by key presence, but respects the model alias
  the user chose (so an LLM7 model stays on LLM7 even when a Perplexity key
  is set).
- Explicit modes bypass the model-alias heuristic.

### 4.3 Perplexity call

```python
POST https://api.perplexity.ai/chat/completions
Authorization: Bearer <PERPLEXITY_API_KEY>
Body: { model, messages, max_tokens: 800, temperature: 0.4 }
```

- `_PERPLEXITY_ALIASES`: `sonar`, `sonar-pro`, `sonar-reasoning`,
  `sonar-reasoning-pro`, `sonar-deep-research`.
- Response normalized by `_extract_content` (handles `message.content`,
  `message.reasoning`, `message.reasoning_content`, `delta.content`).
- `_append_citations` reads the `citations` or `search_results` array and
  appends up to 5 URLs as a `Sources:` footer when the content doesn't
  already contain one.

### 4.4 LLM7 call (fallback)

```python
POST https://api.llm7.io/v1/chat/completions
Body: { model, messages, max_tokens: 800, temperature: 0.7 }
```

- `_LLM7_ALIASES`: `mistral-nemo`, `gpt-oss`, `nemotron`.
- Rate-limit response (429 with `retry_after`) is forwarded to the client as a
  friendly `"Model is rate-limited. Retry in Xs."`.

### 4.5 Fallback behavior

In `auto` mode, a Perplexity error (except 401/403/429) silently retries on
LLM7 with `mistral-nemo`. Auth and rate-limit errors are surfaced so the user
knows to fix the key or wait. In explicit modes, no silent fallback happens.

### 4.6 Error mapping

| Upstream | Our status | Behavior |
|---|---|---|
| Perplexity 2xx with content | 200 | `{model, provider: "perplexity", content}` plus citations footer |
| Perplexity 401/403 | 502 | `"Perplexity rejected credentials. Check PERPLEXITY_API_KEY."` |
| Perplexity 429 | 429 | `"Perplexity rate limit exceeded. Try again shortly."` |
| Perplexity 5xx (auto mode) | — | Silent fallback to LLM7 |
| Perplexity 5xx (explicit mode) | 502 | `"Perplexity returned …"` |
| LLM7 2xx | 200 | `{model, provider: "llm7", content}` |
| LLM7 429 | 429 | `"Model is rate-limited. Retry in Xs."` |
| LLM7 other 4xx/5xx | 502 | `"LLM7 returned …"` |
| Network error | 502 | `"Upstream LLM error: <exc>"` |

### 4.7 Why FastAPI + httpx and not a worker/queue

- Chat is request/response, single-shot, no fan-out — a plain async handler
  is enough.
- Guardian already runs httpx for GitHub API calls, so there's no new
  dependency surface.

## 5. Upstream decision history

| Candidate | Verdict |
|---|---|
| Pollinations.ai | Dropped — Turnstile on browser calls, strict 1/45s free tier. |
| Hack Club AI | Dropped — now requires signup / API key. |
| LLM7.io turbo tier | **Kept** as the no-key fallback. OpenAI-compatible, 3 usable models. |
| Vireonix | Dropped — 502 at test time. |
| Local Ollama / webllm | Dropped for MVP — adds setup burden. |
| **Perplexity Sonar** | **Picked** as primary when a key is available — OpenAI-compatible, web-grounded, citations, strong defaults. |
| OpenAI / Anthropic | Not configured; trivial to add alongside Perplexity using the same provider pattern. |

## 6. Configuration

Three env vars (all optional; defaults keep the free demo path working):

| Variable | Default | Purpose |
|---|---|---|
| `GUARDIAN_CHAT_PROVIDER` | `auto` | `auto` \| `perplexity` \| `llm7` |
| `PERPLEXITY_API_KEY` | *(empty)* | Required for Perplexity routing |
| `PERPLEXITY_DEFAULT_MODEL` | `sonar` | Server-side default when alias is unknown |

Set these in `.env`; `docker-compose.yml` passes them into the Guardian
container.

## 7. Security and privacy

- `PERPLEXITY_API_KEY` lives only in `.env` and the Guardian container's
  environment. Nothing logs or echoes it. CORS limits the dashboard origin
  that can hit the endpoint.
- The disclaimer under the input tells users not to paste secrets.
- Nothing from `.env` or the Guardian DB is included in LLM requests.
- Future hardening (not in this MVP): request logging opt-in, per-IP rate
  limit, prompt-injection scrubbing, content moderation on both ends,
  key rotation workflow.

## 8. Files touched

| File | Change |
|---|---|
| `.env` | Added `GUARDIAN_CHAT_PROVIDER`, `PERPLEXITY_API_KEY`, `PERPLEXITY_DEFAULT_MODEL` |
| `docker-compose.yml` | Passes the three new env vars into Guardian |
| `app/guardian/src/config.py` | New settings for chat provider + Perplexity |
| `app/guardian/src/api/routes.py` | Provider abstraction (`_call_perplexity`, `_call_llm7`), citation footer, `/chat/providers` endpoint |
| `app/dash/package.json` | Added `react-markdown`, `remark-gfm` |
| `app/dash/src/App.tsx` | Route `/chat` |
| `app/dash/src/components/Layout.tsx` | Sidebar entry + icon |
| `app/dash/src/pages/Chat.tsx` | New page: provider probe, model picker, markdown render, strong system prompt |

## 9. Future work

1. **Streaming (SSE)** — swap single-shot for `text/event-stream` so long
   reasoning answers surface token-by-token.
2. **RAG over Guardian DB** — pull latest scan, selected repo, recent
   purchases, and threshold into a dynamic context block so the Assistant
   can answer "what triggered this purchase?" with the actual record.
3. **Server-side conversation storage** — keyed by session, so refresh keeps
   history.
4. **Per-IP rate limiting** at the proxy; prompt-injection scrubbing on
   egress; moderation.
5. **Multi-provider plug-in interface** — formalize `_call_*` into a
   `ChatProvider` protocol so adding OpenAI/Anthropic/Groq is a drop-in file.
6. **First-class citation of IARG docs** in replies (markdown links into
   `MVP.md` and specific dashboard pages).
