'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth'
import { api } from '@/lib/api'

function download(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

export default function McpDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { user, loading } = useAuth()
  const router = useRouter()
  const [mcp, setMcp] = useState<any>(null)
  const [summary, setSummary] = useState<any>(null)
  const [feedback, setFeedback] = useState<any[]>([])
  const [ide, setIde] = useState('kiro')
  const [snippet, setSnippet] = useState<any>(null)
  const [rating, setRating] = useState(5)
  const [comment, setComment] = useState('')
  const [error, setError] = useState('')

  useEffect(() => { if (!loading && !user) router.replace('/login') }, [user, loading, router])

  useEffect(() => {
    if (!user || !id) return
    api.get(`/api/v1/mcps/${id}`).then(setMcp).catch(() => {})
    api.get(`/api/v1/feedback/summary/${id}`).then(setSummary).catch(() => {})
    api.get(`/api/v1/feedback/mcp/${id}`).then(setFeedback).catch(() => {})
  }, [user, id])

  const handleInstall = async () => {
    try {
      const res = await api.post(`/api/v1/mcps/${id}/install`, { ide })
      setSnippet(res.config_snippet)
    } catch (e: unknown) { setError(e instanceof Error ? e.message : 'Install failed') }
  }

  const handleFeedback = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.post('/api/v1/feedback', { listing_id: id, listing_type: 'mcp', rating, comment })
      setComment('')
      api.get(`/api/v1/feedback/mcp/${id}`).then(setFeedback)
      api.get(`/api/v1/feedback/summary/${id}`).then(setSummary)
    } catch (err: unknown) { setError(err instanceof Error ? err.message : 'Feedback failed') }
  }

  const handleDelete = async () => {
    if (!confirm('Delete this MCP server? This cannot be undone.')) return
    try { await api.del(`/api/v1/mcps/${id}`); router.push('/mcps') }
    catch (e: unknown) { setError(e instanceof Error ? e.message : 'Delete failed') }
  }

  if (loading || !user || !mcp) return null
  const canDelete = user.role === 'admin' || mcp.submitted_by === user.id

  const isShellCommand = snippet && typeof snippet === 'object' && snippet.command
  const configStr = snippet ? JSON.stringify(snippet, null, 2) : ''
  const configFilename = ide === 'kiro' ? 'mcp.json' : ide === 'gemini-cli' ? 'mcp-config.json' : 'mcp.json'

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-2xl font-bold">{mcp.name} <span className="text-lg text-gray-500 font-normal">v{mcp.version}</span></h1>
        {canDelete && <button onClick={handleDelete} className="bg-red-600 text-white px-3 py-1 rounded text-sm hover:bg-red-700">Delete</button>}
      </div>
      {error && <div className="bg-red-100 text-red-700 p-3 rounded mb-4">{error}</div>}

      <div className="flex gap-2 mb-4">
        <span className="bg-blue-100 text-blue-700 text-xs px-2 py-0.5 rounded">{mcp.category}</span>
        <span className="text-sm text-gray-500">by {mcp.owner}</span>
        <span className="text-xs text-gray-400">Status: {mcp.status}</span>
      </div>
      <p className="text-gray-700 mb-4">{mcp.description}</p>
      {mcp.git_url && <p className="text-sm text-gray-500 mb-2">Git: <a href={mcp.git_url} className="text-blue-600 hover:underline">{mcp.git_url}</a></p>}
      {mcp.supported_ides?.length > 0 && (
        <div className="flex gap-1 mb-4">{mcp.supported_ides.map((i: string) => <span key={i} className="bg-blue-100 text-blue-700 text-xs px-2 py-0.5 rounded">{i}</span>)}</div>
      )}
      {mcp.setup_instructions && <div className="bg-gray-100 rounded p-3 text-sm mb-6 whitespace-pre-wrap">{mcp.setup_instructions}</div>}

      {/* Install */}
      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <h2 className="font-semibold mb-3">Install for your IDE</h2>
        <div className="flex gap-2 mb-4">
          {['kiro', 'cursor', 'claude-code', 'gemini-cli', 'vscode'].map(i => (
            <button key={i} onClick={() => { setIde(i); setSnippet(null) }}
              className={`px-3 py-1.5 rounded text-sm border ${ide === i ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 hover:bg-gray-50'}`}>
              {i}
            </button>
          ))}
        </div>
        <button onClick={handleInstall} className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm mb-4">Generate Config</button>

        {snippet && (
          <div>
            {isShellCommand ? (
              <div>
                <span className="text-sm font-medium mb-1 block">🖥️ Run this command:</span>
                <pre className="bg-gray-900 text-green-400 p-3 rounded text-sm">{snippet.command}</pre>
                <button onClick={() => navigator.clipboard.writeText(snippet.command).catch(() => {})}
                  className="mt-1 text-xs text-blue-600 hover:underline">Copy command</button>
              </div>
            ) : (
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium">📄 {ide === 'kiro' ? '.kiro/mcp.json' : `.${ide}/mcp.json`}</span>
                  <button onClick={() => download(configFilename, configStr)}
                    className="bg-green-600 text-white px-3 py-1 rounded text-xs hover:bg-green-700">⬇ Download</button>
                </div>
                <pre className="bg-gray-900 text-green-400 p-3 rounded text-xs overflow-x-auto">{configStr}</pre>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Feedback */}
      <div className="bg-white rounded-lg shadow p-4">
        <h2 className="font-semibold mb-3">Feedback</h2>
        {summary && <p className="text-sm text-gray-600 mb-3">Average: {summary.average_rating?.toFixed(1)} ⭐ ({summary.total_reviews} reviews)</p>}
        <form onSubmit={handleFeedback} className="flex gap-2 mb-4">
          <select value={rating} onChange={e => setRating(Number(e.target.value))} className="border rounded px-2 py-1 text-sm">
            {[1, 2, 3, 4, 5].map(n => <option key={n} value={n}>{n} ⭐</option>)}
          </select>
          <input value={comment} onChange={e => setComment(e.target.value)} placeholder="Comment…" className="border rounded px-3 py-1 flex-1 text-sm" />
          <button type="submit" className="bg-blue-600 text-white px-4 py-1 rounded hover:bg-blue-700 text-sm">Submit</button>
        </form>
        <div className="space-y-2">
          {feedback.map((f, i) => (
            <div key={i} className="border-b pb-2 text-sm">
              <span className="font-medium">{f.rating} ⭐</span> <span className="text-gray-600">{f.comment}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
