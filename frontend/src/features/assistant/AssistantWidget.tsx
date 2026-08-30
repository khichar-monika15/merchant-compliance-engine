import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { MessageCircle, Send, X } from 'lucide-react'

import { askAssistant } from '@/api/client'
import type { AssistantTurn } from '@/api/types'
import { Badge, Spinner, cn } from '@/components/ui'

/**
 * Questions worth one tap. Deliberately about the merchant's own report rather than about
 * compliance in general, because that is where the assistant is grounded and most useful.
 */
const SUGGESTIONS = [
  'Why did I get this score?',
  'What should I fix first?',
  'Explain my worst finding in plain English',
]

interface Message extends AssistantTurn {
  cited?: string[]
  failed?: boolean
}

export function AssistantWidget() {
  const { jobId } = useParams<{ jobId: string }>()
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (open) {
      endRef.current?.scrollIntoView({ behavior: 'smooth' })
      inputRef.current?.focus()
    }
  }, [open, messages, pending])

  useEffect(() => {
    if (!open) return
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open])

  async function ask(question: string) {
    const trimmed = question.trim()
    if (!trimmed || pending) return

    // The history sent is the conversation before this question, which is what the backend
    // replays. Sending the new question inside it too would show it to the model twice.
    const history = messages.map(({ role, content }) => ({ role, content }))
    setMessages((m) => [...m, { role: 'user', content: trimmed }])
    setDraft('')
    setPending(true)

    try {
      const reply = await askAssistant(trimmed, jobId, history)
      setMessages((m) => [
        ...m,
        { role: 'assistant', content: reply.answer, cited: reply.cited_checks, failed: !reply.available },
      ])
    } catch {
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          content: 'Something went wrong reaching the assistant. Your report is unaffected.',
          failed: true,
        },
      ])
    } finally {
      setPending(false)
    }
  }

  return (
    <div data-print-hide>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? 'Close the compliance assistant' : 'Open the compliance assistant'}
        className={cn(
          'fixed bottom-5 right-5 z-50 flex h-12 w-12 items-center justify-center rounded-full',
          'bg-accent text-white shadow-lg transition-transform hover:scale-105',
          // The halo breathes on hover so the entry point reads as live rather than decorative.
          'hover:animate-pulse-glow focus-visible:animate-pulse-glow',
          'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2',
        )}
      >
        {open ? <X className="h-5 w-5" /> : <MessageCircle className="h-5 w-5" />}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Compliance assistant"
          className={cn(
            'fixed z-50 flex flex-col overflow-hidden rounded-xl border border-surface-border',
            'bg-surface-raised shadow-2xl',
            // Full width on a phone, a panel on anything larger.
            'inset-x-3 bottom-20 max-h-[70vh]',
            'sm:inset-x-auto sm:right-5 sm:w-[380px] sm:max-h-[560px]',
          )}
        >
          <div className="flex items-center gap-2 border-b border-surface-border px-4 py-3">
            <MessageCircle className="h-4 w-4 text-accent" />
            <span className="text-body-sm font-semibold text-text-primary">
              Compliance assistant
            </span>
            <span className="ml-auto text-caption text-text-tertiary">
              {jobId ? 'Reading your report' : 'General questions'}
            </span>
          </div>

          <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
            {messages.length === 0 && (
              <div className="space-y-3">
                <p className="text-body-sm text-text-secondary">
                  Ask about anything in your report. I read the same rule files the engine scored
                  you against.
                </p>
                <div className="space-y-1.5">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => ask(s)}
                      className={cn(
                        'w-full rounded-lg border border-surface-border px-3 py-2 text-left',
                        'text-body-sm text-text-secondary transition-colors',
                        'hover:border-accent hover:text-text-primary',
                      )}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((message, i) => (
              <div
                key={i}
                className={cn(
                  'max-w-[92%] rounded-lg px-3 py-2 text-body-sm',
                  message.role === 'user'
                    ? 'ml-auto bg-accent-muted text-text-primary'
                    : 'bg-surface text-text-secondary',
                  message.failed && 'border border-status-warning/40',
                )}
              >
                <p className="whitespace-pre-wrap break-words">{message.content}</p>
                {message.cited && message.cited.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {message.cited.map((id) => (
                      <Badge key={id} variant="neutral">
                        {id}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            ))}

            {pending && (
              <div className="flex items-center gap-2 text-caption text-text-tertiary">
                <Spinner size="sm" />
                Reading your report
              </div>
            )}
            <div ref={endRef} />
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault()
              void ask(draft)
            }}
            className="flex items-center gap-2 border-t border-surface-border px-3 py-2"
          >
            <input
              ref={inputRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask about your report"
              aria-label="Ask about your report"
              className={cn(
                'min-w-0 flex-1 bg-transparent px-1 py-1.5 text-body-sm text-text-primary',
                'placeholder:text-text-tertiary focus:outline-none',
              )}
            />
            <button
              type="submit"
              disabled={!draft.trim() || pending}
              aria-label="Send"
              className={cn(
                'rounded p-1.5 text-accent transition-colors hover:bg-surface-hover',
                'disabled:cursor-not-allowed disabled:text-text-tertiary',
              )}
            >
              <Send className="h-4 w-4" />
            </button>
          </form>

          {/*
            Scope here is deliberately wider than the knowledge base, so this is not decoration.
            Answers grounded in a published rule carry the check id as a badge; anything without
            one is the model talking and the reader is told to check it.
          */}
          <p className="border-t border-surface-border px-4 py-2 text-caption text-text-tertiary">
            AI-generated and can be wrong. Tagged answers cite a real check, verify the rest.
          </p>
        </div>
      )}
    </div>
  )
}
