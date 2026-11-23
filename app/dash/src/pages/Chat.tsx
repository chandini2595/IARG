import React, { useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import toast from 'react-hot-toast'
import { guardianApi } from '@/lib/api'

type Role = 'system' | 'user' | 'assistant'

type ChatMessage = {
  role: Role
  content: string
}

type UiMessage = ChatMessage & {
  id: string
  createdAt: number
}

const SYSTEM_PROMPT = `You are the IARG (Intangible-Asset Risk Guardian) assistant inside the IARG dashboard. IARG is a self-hosted product, NOT the public "Industrial Asset Recovery Group" or any ticker symbol — ignore unrelated hits.

Product context (ground your answers in this):
- IARG = Intangible-Asset Risk Guardian: an event-driven system that discovers intangible assets (code repos, Drive files, models), scores risk dynamically, and auto-triggers simulated insurance when risk exceeds a threshold.
- Services (Docker Compose): dashboard (React/Vite on :3000), ingest (Node :3001), graph (Go + Neo4j :8001), score (Python :8002), guardian (FastAPI :8003), plus Kafka, Neo4j, Redis, MinIO, IPFS.
- Risk score (0–100) comes from the Guardian service and blends five normalized factors: commits, open PRs, open issues, exposure (public/private + size), and a stability penalty for stale repos.
- Insurance triggers when risk_score > RISK_THRESHOLD (default 70) and cooldown has elapsed. Two templates: micro_policy (60–79.999) and parametric_policy (>= 80).
- Google Drive breach: POST /api/guardian/google-drive/breach with a resource_id, breach_category, optional description. Uses a synthetic score (default 95) and bypasses the GitHub threshold.
- Dashboard tabs: Monitor (live risk + scan), Assets, Risk Scoring (explainable breakdown), Insurance (purchases + evidence), Assistant (this chat), Settings (threshold, repos, Drive).

Answer style:
- Use short paragraphs and real markdown lists (- item). Use **bold** for key terms.
- When the question is about IARG, answer from the product context above first. Only use web search for clearly external facts.
- For general questions, answer helpfully and concisely.
- When citations exist, keep the "Sources:" tail the backend appends.`

// Calls our Guardian backend, which proxies to a free LLM (LLM7.io).
const CHAT_URL = '/api/guardian/chat'

// Model options are provider-dependent. The Guardian backend reports which
// provider is active via GET /api/guardian/chat/providers; we switch the
// picker contents on page load.
type ModelOption = { value: string; label: string }

const PERPLEXITY_MODELS: ModelOption[] = [
  { value: 'sonar', label: 'Sonar (web-grounded, fast)' },
  { value: 'sonar-pro', label: 'Sonar Pro (higher quality)' },
  { value: 'sonar-reasoning', label: 'Sonar Reasoning (step-by-step)' },
  { value: 'sonar-reasoning-pro', label: 'Sonar Reasoning Pro' },
]

const LLM7_MODELS: ModelOption[] = [
  { value: 'mistral-nemo', label: 'Mistral Nemo Instruct (free)' },
  { value: 'gpt-oss', label: 'GPT-OSS 20B (free)' },
  { value: 'nemotron', label: 'Nemotron Nano 30B (free)' },
]

function newId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function IconSend(props: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={props.className}
    >
      <path d="M22 2 11 13" />
      <path d="M22 2 15 22l-4-9-9-4 20-7Z" />
    </svg>
  )
}

function IconTrash(props: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={props.className}
    >
      <path d="M3 6h18" />
      <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
      <path d="M10 11v6" />
      <path d="M14 11v6" />
    </svg>
  )
}

function IconBot(props: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={props.className}
    >
      <rect x="4" y="7" width="16" height="12" rx="2" />
      <path d="M12 7V3" />
      <circle cx="9" cy="13" r="1" />
      <circle cx="15" cy="13" r="1" />
      <path d="M9 17h6" />
    </svg>
  )
}

function IconUser(props: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={props.className}
    >
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  )
}

const SUGGESTIONS = [
  'What does the IARG dashboard do?',
  'How is a risk score computed in IARG?',
  'When does IARG trigger insurance automatically?',
  'How can I report a Google Drive breach?',
]

async function callChatBackend(
  messages: ChatMessage[],
  model: string,
  signal: AbortSignal,
): Promise<string> {
  const res = await guardianApi.post(
    CHAT_URL,
    { model, messages },
    { signal, timeout: 90_000 },
  )
  const content = res?.data?.content
  if (typeof content === 'string' && content.trim().length > 0) return content
  throw new Error('Empty response from chat backend')
}

export default function Chat() {
  const [provider, setProvider] = useState<'perplexity' | 'llm7' | null>(null)
  const [modelOptions, setModelOptions] = useState<ModelOption[]>(LLM7_MODELS)
  const [model, setModel] = useState<string>(LLM7_MODELS[0].value)
  const [input, setInput] = useState<string>('')
  const [messages, setMessages] = useState<UiMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  // On mount, ask the backend which provider is active and swap the model
  // picker options accordingly.
  useEffect(() => {
    let cancelled = false
    guardianApi
      .get('/api/guardian/chat/providers')
      .then((res) => {
        if (cancelled) return
        const active = res?.data?.active as 'perplexity' | 'llm7' | undefined
        if (active === 'perplexity') {
          setProvider('perplexity')
          setModelOptions(PERPLEXITY_MODELS)
          setModel(PERPLEXITY_MODELS[0].value)
        } else {
          setProvider('llm7')
          setModelOptions(LLM7_MODELS)
          setModel(LLM7_MODELS[0].value)
        }
      })
      .catch(() => {
        // If the probe fails, keep the free-tier models and let the user try.
        setProvider('llm7')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const visibleMessages = useMemo(
    () => messages.filter((m) => m.role !== 'system'),
    [messages],
  )

  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [visibleMessages.length, isLoading])

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  async function send(text: string) {
    const prompt = text.trim()
    if (!prompt || isLoading) return

    const userMsg: UiMessage = {
      id: newId(),
      role: 'user',
      content: prompt,
      createdAt: Date.now(),
    }
    const nextMessages = [...messages, userMsg]
    setMessages(nextMessages)
    setInput('')
    setIsLoading(true)

    const payload: ChatMessage[] = [
      { role: 'system', content: SYSTEM_PROMPT },
      ...nextMessages.map(({ role, content }) => ({ role, content })),
    ]

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const reply = await callChatBackend(payload, model, controller.signal)
      const assistantMsg: UiMessage = {
        id: newId(),
        role: 'assistant',
        content: reply.trim(),
        createdAt: Date.now(),
      }
      setMessages((prev) => [...prev, assistantMsg])
    } catch (err: any) {
      if (err?.name === 'AbortError' || err?.name === 'CanceledError') return
      const detail = err?.response?.data?.detail
      const message =
        (typeof detail === 'string' && detail) ||
        err?.message ||
        'Request failed'
      toast.error(`Chat failed: ${message}`)
      const assistantMsg: UiMessage = {
        id: newId(),
        role: 'assistant',
        content: `_Error contacting model_: ${message}`,
        createdAt: Date.now(),
      }
      setMessages((prev) => [...prev, assistantMsg])
    } finally {
      setIsLoading(false)
      abortRef.current = null
      requestAnimationFrame(() => textareaRef.current?.focus())
    }
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    send(input)
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  function clearConversation() {
    abortRef.current?.abort()
    setMessages([])
    setIsLoading(false)
  }

  function stopGenerating() {
    abortRef.current?.abort()
  }

  return (
    <div className="p-6 min-h-screen bg-gray-950 text-gray-100">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">Assistant</h1>
          <p className="text-gray-300 mt-1">
            {provider === 'perplexity'
              ? 'Chatbot powered by Perplexity Sonar (web-grounded answers with citations).'
              : 'Free chatbot powered by a public LLM endpoint. No API key required.'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="chat-model" className="text-xs text-gray-400">
            Model
          </label>
          <select
            id="chat-model"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="bg-gray-900 border border-primary-500/30 rounded-md px-3 py-1.5 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
          >
            {modelOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={clearConversation}
            className="btn-secondary"
            title="Clear conversation"
            disabled={messages.length === 0 && !isLoading}
          >
            <IconTrash className="w-4 h-4" />
          </button>
        </div>
      </header>

      <div className="card flex flex-col h-[calc(100vh-10rem)] max-w-5xl mx-auto overflow-hidden">
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto px-6 py-5 space-y-5 scroll-smooth"
        >
          {visibleMessages.length === 0 && !isLoading ? (
            <EmptyState onPick={send} />
          ) : (
            <>
              {visibleMessages.map((m) => (
                <MessageBubble key={m.id} message={m} />
              ))}
              {isLoading && <TypingBubble />}
            </>
          )}
        </div>

        <form
          onSubmit={onSubmit}
          className="border-t border-primary-500/20 px-4 py-3 bg-gray-950"
        >
          <div className="flex items-end gap-2">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              rows={2}
              placeholder="Message the assistant…  (Enter to send, Shift+Enter for newline)"
              className="flex-1 resize-none bg-gray-900 border border-primary-500/30 rounded-md px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
              disabled={isLoading}
            />
            {isLoading ? (
              <button
                type="button"
                onClick={stopGenerating}
                className="btn-secondary h-10"
                title="Stop"
              >
                Stop
              </button>
            ) : (
              <button
                type="submit"
                className="btn-primary h-10"
                disabled={!input.trim()}
                title="Send"
              >
                <IconSend className="w-4 h-4" />
              </button>
            )}
          </div>
          <div className="mt-2 text-xs text-gray-400">
            Responses come from a public free model and may be inaccurate. Avoid sending sensitive data.
          </div>
        </form>
      </div>
    </div>
  )
}

function EmptyState({ onPick }: { onPick: (text: string) => void }) {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center py-10">
      <div className="w-14 h-14 rounded-full bg-primary-500/15 border border-primary-500/40 flex items-center justify-center mb-4">
        <IconBot className="w-7 h-7 text-primary-300" />
      </div>
      <h2 className="text-lg font-medium text-gray-100">
        Ask the IARG assistant anything
      </h2>
      <p className="text-sm text-gray-400 mt-1 max-w-md">
        Try one of the prompts below or type your own question.
      </p>
      <div className="mt-5 flex flex-wrap gap-2 justify-center max-w-xl">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => onPick(s)}
            className="px-3 py-1.5 text-xs rounded-full border border-primary-500/30 bg-primary-500/10 text-primary-200 hover:bg-primary-500/20 transition-colors"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  )
}

function MessageBubble({ message }: { message: UiMessage }) {
  const isUser = message.role === 'user'
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div
        className={[
          'w-8 h-8 shrink-0 rounded-full flex items-center justify-center border',
          isUser
            ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
            : 'bg-primary-500/15 border-primary-500/40 text-primary-300',
        ].join(' ')}
      >
        {isUser ? <IconUser className="w-4 h-4" /> : <IconBot className="w-4 h-4" />}
      </div>
      <div
        className={[
          'max-w-[80%] rounded-lg px-4 py-3 text-sm break-words',
          isUser
            ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-50 whitespace-pre-wrap'
            : 'bg-gray-900 border border-primary-500/25 text-gray-100',
        ].join(' ')}
      >
        {isUser ? message.content : <Markdown source={message.content} />}
      </div>
    </div>
  )
}

function Markdown({ source }: { source: string }) {
  return (
    <div className="chat-md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ node, ...props }) => <p className="my-2 first:mt-0 last:mb-0" {...props} />,
          ul: ({ node, ...props }) => <ul className="list-disc pl-5 my-2 space-y-1" {...props} />,
          ol: ({ node, ...props }) => <ol className="list-decimal pl-5 my-2 space-y-1" {...props} />,
          li: ({ node, ...props }) => <li className="leading-snug" {...props} />,
          strong: ({ node, ...props }) => <strong className="font-semibold text-white" {...props} />,
          em: ({ node, ...props }) => <em className="italic" {...props} />,
          h1: ({ node, ...props }) => <h3 className="text-base font-semibold mt-3 mb-1" {...props} />,
          h2: ({ node, ...props }) => <h3 className="text-base font-semibold mt-3 mb-1" {...props} />,
          h3: ({ node, ...props }) => <h3 className="text-sm font-semibold mt-3 mb-1" {...props} />,
          a: ({ node, ...props }) => (
            <a
              className="text-primary-300 underline underline-offset-2 hover:text-primary-200"
              target="_blank"
              rel="noreferrer"
              {...props}
            />
          ),
          code: ({ node, className, children, ...props }: any) => {
            const inline = !className
            if (inline) {
              return (
                <code
                  className="rounded bg-gray-800 px-1.5 py-0.5 text-[0.85em] text-primary-200"
                  {...props}
                >
                  {children}
                </code>
              )
            }
            return (
              <code className={className} {...props}>
                {children}
              </code>
            )
          },
          pre: ({ node, ...props }) => (
            <pre
              className="my-2 overflow-x-auto rounded-md bg-gray-800 p-3 text-xs text-gray-100"
              {...props}
            />
          ),
          blockquote: ({ node, ...props }) => (
            <blockquote
              className="my-2 border-l-2 border-primary-500/40 pl-3 text-gray-300"
              {...props}
            />
          ),
          hr: () => <hr className="my-3 border-primary-500/20" />,
          table: ({ node, ...props }) => (
            <div className="my-2 overflow-x-auto">
              <table className="min-w-full text-xs border border-primary-500/20" {...props} />
            </div>
          ),
          th: ({ node, ...props }) => (
            <th className="border border-primary-500/20 px-2 py-1 text-left font-semibold bg-gray-800" {...props} />
          ),
          td: ({ node, ...props }) => (
            <td className="border border-primary-500/20 px-2 py-1 align-top" {...props} />
          ),
        }}
      >
        {source}
      </ReactMarkdown>
    </div>
  )
}

function TypingBubble() {
  return (
    <div className="flex gap-3">
      <div className="w-8 h-8 shrink-0 rounded-full bg-primary-500/15 border border-primary-500/40 flex items-center justify-center text-primary-300">
        <IconBot className="w-4 h-4" />
      </div>
      <div className="rounded-lg px-4 py-3 bg-gray-900 border border-primary-500/25">
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-primary-300 animate-pulse" />
          <span className="w-1.5 h-1.5 rounded-full bg-primary-300 animate-pulse [animation-delay:150ms]" />
          <span className="w-1.5 h-1.5 rounded-full bg-primary-300 animate-pulse [animation-delay:300ms]" />
        </div>
      </div>
    </div>
  )
}
