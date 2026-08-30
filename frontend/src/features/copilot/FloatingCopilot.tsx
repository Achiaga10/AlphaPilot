import { useQuery } from '@tanstack/react-query'
import { type FormEvent, type KeyboardEvent, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { askGeneralCopilot, askUnifiedCopilot, getCurrentResearchPortfolio } from '../../api/portfolio'
import { ApiError } from '../../api/client'
import type { CopilotAnswer } from '../../types/portfolio'

const MAX_MESSAGES = 20
const HEBREW = /[\u0590-\u05ff]/

type Message = { id: number; role: 'user' | 'assistant' | 'error'; text: string; context: string; answer?: CopilotAnswer }
type RetryRequest = { question: string; userMessageId: number; activeTicker: string | null; pendingIntent: string | null } | null

export const OPEN_COPILOT_EVENT = 'alphapilot:open-copilot'

export function FloatingCopilot() {
  const portfolio = useQuery({ queryKey: ['research-portfolio'], queryFn: ({ signal }) => getCurrentResearchPortfolio(signal) })
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [pending, setPending] = useState(false)
  const [retryRequest, setRetryRequest] = useState<RetryRequest>(null)
  const [activeTicker, setActiveTicker] = useState<string | null>(null)
  const [pendingIntent, setPendingIntent] = useState<string | null>(null)
  const [composerValue, setComposerValue] = useState('')
  const messageId = useRef(0)
  const messagesRef = useRef<HTMLDivElement>(null)
  const positions = useMemo(() => portfolio.data?.positions ?? [], [portfolio.data?.positions])

  useEffect(() => {
    const listener = (event: Event) => {
      const detail = (event as CustomEvent<{ positionId?: string }>).detail
      const selected = positions.find((item) => item.position_id === detail?.positionId)
      if (selected) {
        setActiveTicker(selected.ticker)
        setPendingIntent(null)
      }
      setOpen(true)
    }
    window.addEventListener(OPEN_COPILOT_EVENT, listener)
    return () => window.removeEventListener(OPEN_COPILOT_EVENT, listener)
  }, [positions])

  useLayoutEffect(() => {
    const history = messagesRef.current
    if (open && history && typeof history.scrollTo === 'function') {
      history.scrollTo({ top: history.scrollHeight, behavior: 'auto' })
    }
  }, [messages, open, pending])

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (pending) return
    const question = composerValue.trim()
    if (!question) return
    const userMessageId = ++messageId.current
    const user: Message = { id: userMessageId, role: 'user', text: question, context: activeTicker ?? 'General' }
    setMessages((current) => [...current, user].slice(-MAX_MESSAGES))
    send(question, userMessageId, activeTicker, pendingIntent)
    setComposerValue('')
  }

  function send(question: string, userMessageId: number, requestTicker: string | null, requestPendingIntent: string | null) {
    setPending(true)
    setRetryRequest(null)
    const request = portfolio.data
      ? askUnifiedCopilot(portfolio.data.portfolio_id, { question, active_ticker: requestTicker, pending_intent: requestPendingIntent })
      : askGeneralCopilot(question)
    void request
      .then((answer) => {
        const label = answer.ticker ?? (answer.scope === 'PORTFOLIO' ? 'Portfolio' : 'General')
        setMessages((current) => [
          ...current.map((item) => item.id === userMessageId ? { ...item, context: label } : item),
          { id: ++messageId.current, role: 'assistant' as const, text: answer.answer, context: label, answer },
        ].slice(-MAX_MESSAGES))
        if (answer.resolution_status === 'CLARIFICATION_REQUIRED') {
          setPendingIntent(answer.intent ?? null)
        } else {
          setPendingIntent(null)
          if (answer.ticker && (answer.resolution_status === 'RESOLVED' || answer.resolution_status === 'ENTITY_ESTABLISHED')) setActiveTicker(answer.ticker)
        }
      })
      .catch((caught: unknown) => {
        const code = caught instanceof ApiError ? caught.code : null
        const text = code === 'AI_PROVIDER_UNAVAILABLE'
          ? 'AlphaPilot AI is currently unavailable. Check the local Ollama service and try again.'
          : code === 'AI_RESPONSE_INVALID'
            ? 'AlphaPilot received an invalid AI response. Please retry.'
            : 'AlphaPilot could not complete this request. Please retry.'
        setMessages((current) => [...current, { id: ++messageId.current, role: 'error' as const, text, context: requestTicker ?? 'General' }].slice(-MAX_MESSAGES))
        setRetryRequest({ question, userMessageId, activeTicker: requestTicker, pendingIntent: requestPendingIntent })
      })
      .finally(() => setPending(false))
  }

  function keyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  function clearPositionContext() {
    setActiveTicker(null)
    setPendingIntent(null)
  }

  return <aside className={`floating-copilot ${open ? 'is-open' : ''}`} aria-label="AlphaPilot AI assistant">
    <button className="floating-copilot__trigger" type="button" aria-expanded={open} onClick={() => setOpen((value) => !value)}>Ask AI</button>
    {open ? <section className="floating-copilot__panel">
      <div className="floating-copilot__heading"><div><strong>Ask AlphaPilot AI</strong><small>Read-only · grounded backend facts</small>{activeTicker ? <small>Currently discussing: {activeTicker}</small> : null}</div><div className="floating-copilot__heading-actions">{activeTicker ? <button type="button" className="copilot-context-clear" onClick={clearPositionContext}>Clear position context</button> : null}<button type="button" aria-label="Close AI assistant" onClick={() => setOpen(false)}>×</button></div></div>
      <div className="floating-copilot__messages" ref={messagesRef} aria-label="Copilot message history" aria-live="polite">{messages.length === 0 ? <p>Ask about AlphaPilot, your research portfolio, or name a ticker.</p> : messages.map((message) => <article key={message.id} className={`copilot-message copilot-message--${message.role}`} dir={message.role === 'user' && HEBREW.test(message.text) ? 'rtl' : 'ltr'}><small>{message.context} · {message.role === 'user' ? 'You' : 'AlphaPilot AI'}</small><p>{message.text}</p>{message.answer && message.answer.fact_refs.length > 0 ? <details><summary>Based on AlphaPilot data</summary>{message.answer.fact_refs.map((fact) => <div key={fact.fact_id}><strong>{fact.label}:</strong> {String(fact.value)}</div>)}</details> : null}</article>)}{pending ? <article className="copilot-message copilot-message--assistant copilot-typing" aria-label="AlphaPilot AI is preparing a response"><span>●</span><span>●</span><span>●</span></article> : null}</div>
      <form onSubmit={submit}><label><span>Question</span><textarea name="question" value={composerValue} onChange={(event) => setComposerValue(event.target.value)} maxLength={1000} rows={2} onKeyDown={keyDown} disabled={pending} required /></label><button className="button button--primary button--small" disabled={pending}>Send</button></form>
      {retryRequest ? <button type="button" className="button button--secondary button--small" onClick={() => send(retryRequest.question, retryRequest.userMessageId, retryRequest.activeTicker, retryRequest.pendingIntent)} disabled={pending}>Retry</button> : null}
    </section> : null}
  </aside>
}
