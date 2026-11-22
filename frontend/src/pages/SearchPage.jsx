import { useState } from 'react'

import { api } from '../api/client.js'
import ClauseDialog from '../components/ClauseDialog.jsx'
import { Badge, Card, Empty, ErrorMessage, PageHeader } from '../components/ui.jsx'

const EMPTY = { q: '', doc_type: '', doc_code: '', latest_only: true }

// RAG-2 / RAG-4: semantic + keyword search across regulations and policies.
export default function SearchPage() {
  const [filters, setFilters] = useState(EMPTY)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [openClause, setOpenClause] = useState(null)

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      setResults(await api.search({ ...filters, latest_only: filters.latest_only ? 'true' : 'false' }))
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader title="Search" subtitle="Find related clauses across regulations, policies and guidelines." />
      <Card>
        <form className="search-form" onSubmit={submit}>
          <input
            className="search-input"
            value={filters.q}
            onChange={(e) => setFilters({ ...filters, q: e.target.value })}
            placeholder="e.g. reporting threshold for cash transactions"
            minLength={2}
            required
          />
          <select value={filters.doc_type} onChange={(e) => setFilters({ ...filters, doc_type: e.target.value })}>
            <option value="">All types</option>
            <option value="regulation">Regulations</option>
            <option value="policy">Policies</option>
            <option value="guideline">Guidelines</option>
          </select>
          <input
            value={filters.doc_code}
            onChange={(e) => setFilters({ ...filters, doc_code: e.target.value })}
            placeholder="Document code"
          />
          <label className="toggle">
            <input
              type="checkbox"
              checked={filters.latest_only}
              onChange={(e) => setFilters({ ...filters, latest_only: e.target.checked })}
            />
            Latest versions only
          </label>
          <button type="submit" className="button primary" disabled={busy}>
            {busy ? 'Searching…' : 'Search'}
          </button>
        </form>
      </Card>
      <ErrorMessage error={error} />
      {results?.length === 0 && <Empty>No matching clauses.</Empty>}
      <div className="results">
        {results?.map((hit) => (
          <button key={hit.clause_id} type="button" className="result" onClick={() => setOpenClause(hit.clause_id)}>
            <div className="result-head">
              <strong>
                {hit.doc_code} §{hit.clause_number}
              </strong>
              <Badge>{hit.doc_type}</Badge>
              <span className="muted small">
                v{hit.version_label} · p.{hit.page}
                {hit.section ? ` · ${hit.section}` : ''}
              </span>
            </div>
            <p>{hit.text}</p>
          </button>
        ))}
      </div>
      {openClause && <ClauseDialog clauseId={openClause} onClose={() => setOpenClause(null)} />}
    </>
  )
}
