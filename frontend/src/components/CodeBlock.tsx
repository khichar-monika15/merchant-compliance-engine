import { useState } from 'react'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { IntegrationResult } from '../types'

const LANG_MAP: Record<string, string> = {
  tsx: 'tsx',
  ts: 'typescript',
  jsx: 'jsx',
  js: 'javascript',
  py: 'python',
  php: 'php',
  html: 'html',
  vue: 'html',
}

interface Props {
  integration: IntegrationResult
}

export function CodeBlock({ integration }: Props) {
  const [copied, setCopied] = useState(false)

  const lang = LANG_MAP[integration.language] ?? 'javascript'

  const copy = () => {
    navigator.clipboard.writeText(integration.starter_code).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h2 className="text-lg font-semibold">Integration Starter Code</h2>
          <p className="text-sm text-gray-500 mt-1">
            Detected stack: <strong>{integration.detected_stack}</strong> — Recommended: <strong>{integration.recommended_product}</strong>
          </p>
        </div>
        <button onClick={copy} className="text-xs px-2 py-1 border border-gray-200 rounded hover:bg-gray-50">
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      {integration.recommendations.length > 0 && (
        <ul className="mb-4 space-y-1">
          {integration.recommendations.map((r, i) => (
            <li key={i} className="text-sm text-blue-600">• {r}</li>
          ))}
        </ul>
      )}
      <div className="rounded-lg overflow-hidden text-xs">
        <SyntaxHighlighter language={lang} style={oneLight} customStyle={{ margin: 0, borderRadius: 8, fontSize: '0.75rem' }}>
          {integration.starter_code}
        </SyntaxHighlighter>
      </div>
    </div>
  )
}
