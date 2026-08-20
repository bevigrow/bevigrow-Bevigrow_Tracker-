/**
 * Typing at the campaign instead of clicking it.
 *
 * The replies are assembled on the server from database queries — the same
 * ones behind the status panel — so a number here and a number on the panel
 * cannot disagree. The model, when there is one, only works out which of a
 * fixed list of actions you meant. It never carries a total.
 */
import { CornerDownLeft, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { Card } from './ui'
import { ApiError, api } from '../lib/api'
import { useToast } from '../lib/toast'

interface Line {
  from: 'you' | 'agent'
  text: string
  acted?: boolean
}

const SUGGESTIONS = ['status', 'continue', 'how many are left?', 'show failed']

export function OutreachChat({ onActed }: { onActed?: () => void }) {
  const toast = useToast()
  const [lines, setLines] = useState<Line[]>([
    {
      from: 'agent',
      text: 'Ask me for the status, or tell me to start, pause or stop. Try “status”.',
    },
  ])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'nearest' })
  }, [lines])

  const send = async (message: string) => {
    const trimmed = message.trim()
    if (!trimmed || busy) return
    setLines((l) => [...l, { from: 'you', text: trimmed }])
    setText('')
    setBusy(true)
    try {
      const reply = await api.outreachChat(trimmed)
      setLines((l) => [...l, { from: 'agent', text: reply.reply, acted: reply.acted }])
      if (reply.acted) onActed?.()
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'The assistant did not answer.'
      setLines((l) => [...l, { from: 'agent', text: message }])
      toast.error(message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <div className="mb-3 flex items-center gap-2.5">
        <Sparkles size={17} className="text-gold" />
        <div>
          <h2 className="font-display text-lg text-latte">Ask the agent</h2>
          <p className="text-[11px] text-latte/45">
            Every figure comes from the database, not from the model.
          </p>
        </div>
      </div>

      <div className="max-h-72 space-y-2.5 overflow-y-auto pr-1">
        {lines.map((line, i) => (
          <div
            key={i}
            className={line.from === 'you' ? 'flex justify-end' : 'flex justify-start'}
          >
            <div
              className={
                line.from === 'you'
                  ? 'max-w-[85%] rounded-2xl rounded-br-sm bg-gold/15 px-3.5 py-2 text-[12.5px] text-latte'
                  : 'max-w-[92%] rounded-2xl rounded-bl-sm border border-caramel/15 bg-bean/40 px-3.5 py-2 text-[12.5px] leading-relaxed text-latte/80'
              }
            >
              {line.text.split('\n').map((part, j) => (
                <p key={j} className={j ? 'mt-1' : ''}>
                  {/* **bold** is the only markup the server uses. */}
                  {part.split(/(\*\*[^*]+\*\*)/g).map((chunk, k) =>
                    chunk.startsWith('**') && chunk.endsWith('**') ? (
                      <span key={k} className="font-semibold text-latte">
                        {chunk.slice(2, -2)}
                      </span>
                    ) : (
                      <span key={k}>{chunk}</span>
                    ),
                  )}
                </p>
              ))}
              {line.acted && (
                <p className="mt-1 text-[10.5px] uppercase tracking-wider text-gold/80">
                  Campaign changed
                </p>
              )}
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          void send(text)
        }}
        className="mt-3"
      >
        <div className="relative">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={busy ? 'Thinking…' : 'Tell the agent what to do…'}
            disabled={busy}
            aria-label="Message the outreach agent"
            className="input-field pr-10"
          />
          <button
            type="submit"
            disabled={busy || !text.trim()}
            aria-label="Send"
            className="absolute right-3 top-1/2 -translate-y-1/2 text-latte/35 transition hover:text-gold disabled:opacity-40"
          >
            <CornerDownLeft size={15} />
          </button>
        </div>
      </form>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => void send(s)}
            disabled={busy}
            className="chip border-caramel/25 bg-bean/40 text-[10.5px] normal-case tracking-normal text-latte/55 hover:border-gold/40 hover:text-latte"
          >
            {s}
          </button>
        ))}
      </div>
    </Card>
  )
}
