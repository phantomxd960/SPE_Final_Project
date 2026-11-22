import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { api } from '../api/client.js'
import { Card, ChangeBadge, Empty, ErrorMessage, Loading, PageHeader, StatusBadge } from '../components/ui.jsx'
import { useApi } from '../hooks/useApi.js'
import { CHANGE_ORDER, isActive } from '../lib/changes.js'

function NewComparison({ onCreated }) {
  const navigate = useNavigate()
  const { data: documents } = useApi(() => api.documents(), [])
  const [docId, setDocId] = useState('')
  const [oldId, setOldId] = useState('')
  const [newId, setNewId] = useState('')
  const [error, setError] = useState(null)

  const comparable = useMemo(() => (documents ?? []).filter((d) => d.versions.length >= 2), [documents])
  const versions = comparable.find((d) => String(d.id) === docId)?.versions ?? []

  function chooseDocument(id) {
    setDocId(id)
    const chosen = comparable.find((d) => String(d.id) === id)?.versions ?? []
    setOldId(chosen.at(-2) ? String(chosen.at(-2).id) : '')
    setNewId(chosen.at(-1) ? String(chosen.at(-1).id) : '')
  }

  async function submit(event) {
    event.preventDefault()
    setError(null)
    try {
      const comparison = await api.createComparison(Number(oldId), Number(newId))
      onCreated()
      navigate(`/comparisons/${comparison.id}`)
    } catch (err) {
      setError(err)
    }
  }

  return (
    <Card title="New comparison">
      <form className="form-grid" onSubmit={submit}>
        <ErrorMessage error={error} />
        <label className="field span-2">
          <span>Document</span>
          <select value={docId} onChange={(e) => chooseDocument(e.target.value)} required>
            <option value="">Choose a document with two or more versions</option>
            {comparable.map((doc) => (
              <option key={doc.id} value={doc.id}>
                {doc.doc_code} · {doc.title}
              </option>
            ))}
          </select>
        </label>
        {['Old version', 'New version'].map((label, index) => {
          const [value, setValue] = index === 0 ? [oldId, setOldId] : [newId, setNewId]
          return (
            <label key={label} className="field">
              <span>{label}</span>
              <select value={value} onChange={(e) => setValue(e.target.value)} required disabled={!docId}>
                <option value="" />
                {versions.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.version_label} ({v.status})
                  </option>
                ))}
              </select>
            </label>
          )
        })}
        <div className="span-2">
          <button type="submit" className="button primary" disabled={!oldId || !newId}>
            Compare
          </button>
        </div>
      </form>
    </Card>
  )
}

export default function ComparisonsPage() {
  const anyActive = (items) => items.some((c) => isActive(c.status))
  const { data: comparisons, error, loading, refresh } = useApi(() => api.comparisons(), [], { poll: anyActive })

  return (
    <>
      <PageHeader title="Comparisons" subtitle="Detect what changed between two versions and what it affects." />
      <div className="two-columns">
        <Card title="Recent comparisons">
          <ErrorMessage error={error} />
          {loading && !comparisons && <Loading />}
          {comparisons?.length === 0 && <Empty>No comparisons yet.</Empty>}
          {comparisons?.length > 0 && (
            <table className="table">
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Versions</th>
                  <th>Changes</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {comparisons.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <Link to={`/comparisons/${c.id}`}>
                        <strong>{c.doc_code}</strong>
                      </Link>
                      <div className="muted small">{c.doc_title}</div>
                    </td>
                    <td>
                      {c.old_version} → {c.new_version}
                    </td>
                    <td className="badges">
                      {CHANGE_ORDER.filter((t) => t !== 'unchanged' && c.counts[t]).map((type) => (
                        <span key={type}>
                          <ChangeBadge type={type} /> {c.counts[type]}
                        </span>
                      ))}
                    </td>
                    <td title={c.error ?? ''}>
                      <StatusBadge status={c.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
        <NewComparison onCreated={refresh} />
      </div>
    </>
  )
}
