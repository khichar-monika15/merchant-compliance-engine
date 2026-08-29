import { useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

import { cn } from './cn'

/** Backend `starter_code_language` values mapped to Prism grammars. */
const LANG_MAP: Record<string, string> = {
  typescript: 'typescript',
  tsx: 'tsx',
  javascript: 'javascript',
  jsx: 'jsx',
  vue: 'markup',
  html: 'markup',
  markup: 'markup',
  python: 'python',
  php: 'php',
  ruby: 'ruby',
  markdown: 'markdown',
  json: 'json',
  bash: 'bash',
}

export interface CodeBlockProps {
  code: string
  language?: string
  /** Shown as a label in the header, e.g. the file name or stack. */
  title?: string
  className?: string
  maxHeight?: string
}

export function CodeBlock({
  code,
  language = 'javascript',
  title,
  className,
  maxHeight = '28rem',
}: CodeBlockProps) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    // navigator.clipboard is undefined on an insecure non-localhost origin, which a LAN demo hits
    if (!navigator.clipboard) return
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // A denied clipboard permission must not take the page down
    }
  }

  return (
    <div className={cn('overflow-hidden rounded-lg border border-surface-border', className)}>
      <div className="flex items-center justify-between border-b border-surface-border bg-surface-raised px-3 py-2">
        <span className="text-overline uppercase text-text-tertiary">{title ?? language}</span>
        <button
          type="button"
          onClick={copy}
          className="inline-flex items-center gap-1.5 rounded px-2 py-1 text-caption text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
        >
          {copied ? <Check className="h-3.5 w-3.5 text-status-success" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <div className="overflow-auto" style={{ maxHeight }}>
        <SyntaxHighlighter
          language={LANG_MAP[language] ?? 'javascript'}
          style={oneDark}
          customStyle={{
            margin: 0,
            background: '#070e1c',
            fontSize: '0.8125rem',
            padding: '1rem',
          }}
          codeTagProps={{ style: { fontFamily: '"JetBrains Mono", monospace' } }}
        >
          {code}
        </SyntaxHighlighter>
      </div>
    </div>
  )
}
