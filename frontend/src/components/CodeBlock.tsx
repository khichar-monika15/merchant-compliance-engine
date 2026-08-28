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

  const lang = LANG_MAP[integration.starter_code_language] ?? 'javascript'

  const copy = () => {
    navigator.clipboard.writeText(integration.starter_code).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  // detected_stack is Record<string, string[]> — show framework names
  const stackNames = Object.keys(integration.detected_stack)
    .filter((k) => (integration.detected_stack[k]?.length ?? 0) > 0)
    .join(', ')

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h2 className="text-lg font-semibold">Integration Starter Code</h2>
          <p className="text-sm text-gray-500 mt-1">
            {stackNames && <>Detected: <strong>{stackNames}</strong> — </>}
            Recommended: <strong>{integration.recommended_product}</strong>
            {integration.integration_method && (
              <> via <strong>{integration.integration_method}</strong></>
            )}
          </p>
        </div>
        <button
          onClick={copy}
          className="text-xs px-2 py-1 border border-gray-200 rounded hover:bg-gray-50"
        >
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <div className="rounded-lg overflow-hidden text-xs">
        <SyntaxHighlighter
          language={lang}
          style={oneLight}
          customStyle={{ margin: 0, borderRadius: 8, fontSize: '0.75rem' }}
        >
          {integration.starter_code}
        </SyntaxHighlighter>
      </div>
    </div>
  )
}
