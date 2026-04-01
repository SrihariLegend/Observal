'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/lib/auth'
import { api } from '@/lib/api'

interface AgentItem { id: string; name: string; version: string; description: string; owner: string; model_name: string; supported_ides: string[]; status: string }
interface McpOption { id: string; name: string }
interface Section { name: string; description: string; grounding_required: boolean }
interface ExtMcp { name: string; command: string; args: string; env: string; url: string }

export default function AgentsPage() {
  const { user, loading } = useAuth()
  const router = useRouter()
  const [agents, setAgents] = useState<AgentItem[]>([])
  const [search, setSearch] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [mcpOptions, setMcpOptions] = useState<McpOption[]>([])
  const [form, setForm] = useState({ name: '', version: '1.0.0', description: '', owner: '', prompt: '', model_name: 'claude-sonnet-4', mcp_ids: [] as string[], goal_desc: '' })
  const [selectedIdes, setSelectedIdes] = useState<string[]>(['cursor', 'kiro'])
  const [sections, setSections] = useState<Section[]>([{ name: '', description: '', grounding_required: false }])
  const [extMcps, setExtMcps] = useState<ExtMcp[]>([])
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => { if (!loading && !user) router.replace('/login') }, [user, loading, router])

  const fetchAgents = () => {
    if (!user) return
    const params = search ? `?search=${search}` : ''
    api.get(`/api/v1/agents${params}`).then(setAgents).catch(() => {})
  }
  useEffect(fetchAgents, [user, search])

  useEffect(() => {
    if (showForm) api.get('/api/v1/mcps').then(setMcpOptions).catch(() => {})
  }, [showForm])

  const toggleMcp = (id: string) => {
    setForm(f => ({ ...f, mcp_ids: f.mcp_ids.includes(id) ? f.mcp_ids.filter(x => x !== id) : [...f.mcp_ids, id] }))
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(''); setSuccess('')
    const validSections = sections.filter(s => s.name.trim())
    if (!validSections.length) { setError('At least one goal section is required'); return }
    try {
      const res = await api.post('/api/v1/agents', {
        name: form.name, version: form.version, description: form.description, owner: form.owner,
        prompt: form.prompt, model_name: form.model_name,
        model_config_json: { max_tokens: 4096, temperature: 0.2 },
        supported_ides: selectedIdes,
        mcp_server_ids: form.mcp_ids,
        external_mcps: extMcps.filter(m => m.name.trim()).map(m => ({
          name: m.name, command: m.command || 'npx',
          args: m.args ? m.args.split(' ').filter(Boolean) : [],
          env: m.env ? Object.fromEntries(m.env.split(',').filter(Boolean).map(kv => kv.split('=').map(s => s.trim()))) : {},
          url: m.url || null,
        })),
        goal_template: { description: form.goal_desc, sections: validSections },
      })
      setSuccess(`Agent created! ID: ${res.id}`)
      setShowForm(false)
      fetchAgents()
    } catch (err: unknown) { setError(err instanceof Error ? err.message : 'Create failed') }
  }

  if (loading || !user) return null
  const canCreate = user.role === 'admin' || user.role === 'developer'

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Agent Registry</h1>
        {canCreate && (
          <button onClick={() => setShowForm(!showForm)} className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm">
            {showForm ? 'Cancel' : '+ Create Agent'}
          </button>
        )}
      </div>

      {error && <div className="bg-red-100 text-red-700 p-3 rounded mb-4">{error}</div>}
      {success && <div className="bg-green-100 text-green-700 p-3 rounded mb-4">{success}</div>}

      {showForm && (
        <form onSubmit={submit} className="bg-white border rounded p-4 mb-6 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Agent Name *" required className="border rounded px-3 py-2 text-sm" />
            <input value={form.version} onChange={e => setForm({ ...form, version: e.target.value })} placeholder="Version *" required className="border rounded px-3 py-2 text-sm" />
            <input value={form.owner} onChange={e => setForm({ ...form, owner: e.target.value })} placeholder="Owner / Team *" required className="border rounded px-3 py-2 text-sm" />
            <input value={form.model_name} onChange={e => setForm({ ...form, model_name: e.target.value })} placeholder="Model Name *" required className="border rounded px-3 py-2 text-sm" />
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
          <textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="Description — min 100 characters *" required rows={2} className="w-full border rounded px-3 py-2 text-sm" />
          <textarea value={form.prompt} onChange={e => setForm({ ...form, prompt: e.target.value })} placeholder="System Prompt — min 50 characters *" required rows={3} className="w-full border rounded px-3 py-2 text-sm" />

          {mcpOptions.length > 0 && (
            <div>
              <p className="text-sm font-medium mb-1">Link MCP Servers:</p>
              <div className="flex flex-wrap gap-2">
                {mcpOptions.map(m => (
                  <label key={m.id} className={`text-xs px-3 py-1 rounded border cursor-pointer ${form.mcp_ids.includes(m.id) ? 'bg-blue-100 border-blue-400' : 'bg-gray-50'}`}>
                    <input type="checkbox" checked={form.mcp_ids.includes(m.id)} onChange={() => toggleMcp(m.id)} className="sr-only" />
                    {m.name}
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* External MCPs */}
          <div>
            <p className="text-sm font-medium mb-1">External MCP Servers (any MCP, not in registry):</p>
            {extMcps.map((m, i) => (
              <div key={i} className="grid grid-cols-5 gap-2 mb-1">
                <input value={m.name} onChange={e => { const n = [...extMcps]; n[i].name = e.target.value; setExtMcps(n) }} placeholder="Name *" className="border rounded px-2 py-1 text-sm" />
                <input value={m.command} onChange={e => { const n = [...extMcps]; n[i].command = e.target.value; setExtMcps(n) }} placeholder="Command (npx)" className="border rounded px-2 py-1 text-sm" />
                <input value={m.args} onChange={e => { const n = [...extMcps]; n[i].args = e.target.value; setExtMcps(n) }} placeholder="Args (space-sep)" className="border rounded px-2 py-1 text-sm" />
                <input value={m.url} onChange={e => { const n = [...extMcps]; n[i].url = e.target.value; setExtMcps(n) }} placeholder="Source URL" className="border rounded px-2 py-1 text-sm" />
                <button type="button" onClick={() => setExtMcps(extMcps.filter((_, j) => j !== i))} className="text-red-500 text-sm">✕</button>
              </div>
            ))}
            <button type="button" onClick={() => setExtMcps([...extMcps, { name: '', command: 'npx', args: '', env: '', url: '' }])} className="text-blue-600 text-xs mt-1">+ Add External MCP</button>
            <p className="text-xs text-gray-400 mt-1">e.g., Name: &quot;github-mcp&quot;, Command: &quot;npx&quot;, Args: &quot;-y @modelcontextprotocol/server-github&quot;</p>
          </div>

          <div>
            <p className="text-sm font-medium mb-1">Goal Template:</p>
            <input value={form.goal_desc} onChange={e => setForm({ ...form, goal_desc: e.target.value })} placeholder="Goal description *" required className="w-full border rounded px-3 py-2 text-sm mb-2" />
            {sections.map((s, i) => (
              <div key={i} className="flex gap-2 mb-1">
                <input value={s.name} onChange={e => { const ns = [...sections]; ns[i].name = e.target.value; setSections(ns) }} placeholder="Section name" className="border rounded px-2 py-1 text-sm flex-1" />
                <label className="flex items-center gap-1 text-xs">
                  <input type="checkbox" checked={s.grounding_required} onChange={e => { const ns = [...sections]; ns[i].grounding_required = e.target.checked; setSections(ns) }} />
                  Grounding
                </label>
                {sections.length > 1 && <button type="button" onClick={() => setSections(sections.filter((_, j) => j !== i))} className="text-red-500 text-sm">✕</button>}
              </div>
            ))}
            <button type="button" onClick={() => setSections([...sections, { name: '', description: '', grounding_required: false }])} className="text-blue-600 text-xs mt-1">+ Add Section</button>
          </div>

          <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm">Create Agent</button>
        </form>
      )}

      <div className="mb-6">
        <input placeholder="Search agents…" value={search} onChange={e => setSearch(e.target.value)} className="border rounded px-3 py-2 w-full text-sm" />
      </div>

      <div className="grid grid-cols-3 gap-4">
        {agents.map(a => (
          <div key={a.id} className="bg-white rounded-lg shadow p-4 flex flex-col">
            <div className="flex items-center justify-between mb-2">
              <h2 className="font-semibold text-blue-700">{a.name}</h2>
              <span className="text-xs text-gray-500">v{a.version}</span>
            </div>
            <span className="text-xs text-gray-500 mb-2">{a.model_name}</span>
            <p className="text-sm text-gray-600 flex-1">{a.description?.slice(0, 100)}{a.description?.length > 100 ? '…' : ''}</p>
            <div className="flex items-center justify-between mt-3 text-sm">
              <span className="text-gray-400">{a.owner}</span>
              <Link href={`/agents/${a.id}`} className="text-blue-600 hover:underline">View →</Link>
            </div>
          </div>
        ))}
        {!agents.length && <p className="text-gray-500 col-span-3 text-center py-8">No agents found.</p>}
      </div>
    </div>
  )
}
