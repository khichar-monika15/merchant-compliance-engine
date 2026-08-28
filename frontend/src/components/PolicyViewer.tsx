import { useState } from 'react'
import { PolicyGenResult } from '../types'

interface Props {
  policyGen: PolicyGenResult
}

export function PolicyViewer({ policyGen }: Props) {
  const [activeTab, setActiveTab] = useState(0)
  const [copied, setCopied] = useState(false)

  const policies = policyGen.generated_policies
  if (policies.length === 0) {
    return null
  }

  // A later scan can return fewer policies than the tab index left over from the previous one
  const active = policies[Math.min(activeTab, policies.length - 1)]

  const copy = () => {
    if (!navigator.clipboard) return
    navigator.clipboard.writeText(active.content).then(
      () => {
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      },
      () => setCopied(false),
    )
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h2 className="text-lg font-semibold mb-4">Generated Policies</h2>
      <div className="flex gap-2 mb-4 flex-wrap">
        {policies.map((p, i) => (
          <button
            key={p.policy_type}
            onClick={() => setActiveTab(i)}
            className={`text-sm px-3 py-1.5 rounded-lg border transition-colors ${activeTab === i ? 'bg-blue-600 text-white border-blue-600' : 'border-gray-200 text-gray-600 hover:bg-gray-50'}`}
          >
            {p.policy_type}
          </button>
        ))}
      </div>
      <div className="flex justify-between items-center mb-2">
        <span className="text-xs text-gray-400">{active.word_count} words</span>
        <button onClick={copy} className="text-xs px-2 py-1 border border-gray-200 rounded hover:bg-gray-50">
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <pre className="bg-gray-50 rounded-lg p-4 text-xs text-gray-700 overflow-auto max-h-96 whitespace-pre-wrap font-mono">
        {active.content}
      </pre>
    </div>
  )
}
