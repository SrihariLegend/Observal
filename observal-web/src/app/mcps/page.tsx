'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/lib/auth'
import { api } from '@/lib/api'

interface Mcp {
  id: string; name: string; version: string; description: string; category: string; owner: string; supported_ides: string[]; status: string
}

export default function McpsPage() {
  const { user, loading } = useAuth()
  const router = useRouter()
  const [mcps, setMcps] = useState<Mcp[]>([])
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ git_url: '', name: '', version: '1.0.0', description: '', category: 'utilities', owner: '', changelog: 'Initial release' })
  const [selectedIdes, setSelectedIdes] = useState<string[]>(['cursor', 'kiro'])
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => { if (!loading && !user) router.replace('/login') }, [user, loading, router])

  const fetchMcps = () => {
    if (!user) return
    const params = new URLSearchParams()
    if (search) params.set('search', search)
    if (category) params.set('category', category)
    api.get(`/api/v1/mcps?${params}`).then(setMcps).catch(() => {})
  }
  useEffect(fetchMcps, [user, search, category])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(''); setSuccess('')
    try {
      const res = await api.post('/api/v1/mcps/submit', {
        ...form,
        supported_ides: selectedIdes,
      })
      setSuccess(`Submitted! ID: ${res.id} — Status: ${res.status}`)
      setShowForm(false)
      setForm({ git_url: '', name: '', version: '1.0.0', description: '', category: 'utilities', owner: '', changelog: 'Initial release' })
    } catch (err: unknown) { setError(err instanceof Error ? err.message : 'Submit failed') }
  }

  if (loading || !user) return null
  const canCreate = user.role === 'admin' || user.role === 'developer'

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">MCP Registry</h1>
        {canCreate && (
          <button onClick={() => setShowForm(!showForm)} className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm">
            {showForm ? 'Cancel' : '+ Submit MCP'}
          </button>
        )}
      </div>

      {error && <div className="bg-red-100 text-red-700 p-3 rounded mb-4">{error}</div>}
      {success && <div className="bg-green-100 text-green-700 p-3 rounded mb-4">{success}</div>}

      {showForm && (
        <form onSubmit={submit} className="bg-white border rounded p-4 mb-6 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <input value={form.git_url} onChange={e => setForm({ ...form, git_url: e.target.value })} placeholder="Git URL *" required className="border rounded px-3 py-2 text-sm" />
            <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Name *" required className="border rounded px-3 py-2 text-sm" />
            <input value={form.version} onChange={e => setForm({ ...form, version: e.target.value })} placeholder="Version *" required className="border rounded px-3 py-2 text-sm" />
            <input value={form.category} onChange={e => setForm({ ...form, category: e.target.value })} placeholder="Category *" required className="border rounded px-3 py-2 text-sm" />
            <input value={form.owner} onChange={e => setForm({ ...form, owner: e.target.value })} placeholder="Owner / Team *" required className="border rounded px-3 py-2 text-sm" />
          </div>
          <div className="mb-2">
            <p className="text-sm font-medium mb-1">Supported IDEs:</p>
            <div className="flex flex-wrap gap-2">
              {['cursor', 'kiro', 'claude-code', 'gemini-cli', 'vscode', 'windsurf'].map(ide => (
                <label key={ide} className={`text-xs px-3 py-1.5 rounded border cursor-pointer select-none ${selectedIdes.includes(ide) ? 'bg-blue-100 border-blue-400 text-blue-700' : 'bg-gray-50 text-gray-600'}`}>
                  <input type="checkbox" checked={selectedIdes.includes(ide)} onChange={() => setSelectedIdes(prev => prev.includes(ide) ? prev.filter(x => x !== ide) : [...prev, ide])} className="sr-only" />
                  {ide}
                </label>
              ))}
            </div>
          </div>
          <textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="Description — min 100 characters *" required rows={3} className="w-full border rounded px-3 py-2 text-sm" />
          <input value={form.changelog} onChange={e => setForm({ ...form, changelog: e.target.value })} placeholder="Changelog" className="w-full border rounded px-3 py-2 text-sm" />
          <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm">Submit for Review</button>
        </form>
      )}

      <div className="flex gap-4 mb-6">
        <input placeholder="Search…" value={search} onChange={e => setSearch(e.target.value)} className="border rounded px-3 py-2 flex-1 text-sm" />
        <select value={category} onChange={e => setCategory(e.target.value)} className="border rounded px-3 py-2 text-sm">
          <option value="">All Categories</option>
          {['utilities', 'code-generation', 'database', 'devops', 'testing', 'documentation', 'security'].map(c => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {mcps.map(m => (
          <div key={m.id} className="bg-white rounded-lg shadow p-4 flex flex-col">
            <div className="flex items-center justify-between mb-2">
              <h2 className="font-semibold text-blue-700">{m.name}</h2>
              <span className="text-xs text-gray-500">v{m.version}</span>
            </div>
            <span className="inline-block bg-blue-100 text-blue-700 text-xs px-2 py-0.5 rounded mb-2 w-fit">{m.category}</span>
            <p className="text-sm text-gray-600 flex-1">{m.description?.slice(0, 100)}{m.description?.length > 100 ? '…' : ''}</p>
            <div className="flex items-center justify-between mt-3 text-sm">
              <span className="text-gray-400">{m.owner}</span>
              <Link href={`/mcps/${m.id}`} className="text-blue-600 hover:underline">View →</Link>
            </div>
          </div>
        ))}
        {!mcps.length && <p className="text-gray-500 col-span-3 text-center py-8">No MCP servers found.</p>}
      </div>
    </div>
  )
}
