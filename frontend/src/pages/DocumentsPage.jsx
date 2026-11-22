import { useRef, useState } from 'react'

import { api } from '../api/client.js'
import { Badge, Card, Empty, ErrorMessage, Loading, PageHeader, StatusBadge } from '../components/ui.jsx'
import { useApi } from '../hooks/useApi.js'
import { isActive } from '../lib/changes.js'

const EMPTY_FORM = { doc_code: '', title: '', doc_type: 'regulation', version_label: '', authority: '', effective_date: '' }

function UploadForm({ onUploaded }) {
  const [form, setForm] = useState(EMPTY_FORM)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const fileRef = useRef(null)
  const update = (field) => (event) => setForm({ ...form, [field]: event.target.value })

  async function submit(event) {
    event.preventDefault()
    const data = new FormData()
    Object.entries(form).forEach(([key, value]) => value && data.append(key, value))
    data.append('file', fileRef.current.files[0])
    setBusy(true)
    setError(null)
    try {
      await api.upload(data)
      setForm({ ...EMPTY_FORM, doc_type: form.doc_type })
      fileRef.current.value = ''
      onUploaded()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="Upload a version">
      <form className="form-grid" onSubmit={submit}>
        <ErrorMessage error={error} />
        <label className="field">
          <span>Document code</span>
          <input value={form.doc_code} onChange={update('doc_code')} placeholder="REG001" required />
        </label>
        <label className="field">
          <span>Type</span>
          <select value={form.doc_type} onChange={update('doc_type')}>
            <option value="regulation">Regulation</option>
            <option value="policy">Internal policy</option>
            <option value="guideline">Guideline</option>
          </select>
        </label>
        <label className="field span-2">
          <span>Title</span>
          <input value={form.title} onChange={update('title')} placeholder="Transaction Reporting Regulation" required />
        </label>
        <label className="field">
          <span>Version label</span>
          <input value={form.version_label} onChange={update('version_label')} placeholder="2.0" required />
        </label>
        <label className="field">
          <span>Effective date</span>
          <input type="date" value={form.effective_date} onChange={update('effective_date')} />
        </label>
        <label className="field span-2">
          <span>Authority (optional)</span>
          <input value={form.authority} onChange={update('authority')} placeholder="Financial Conduct Board" />
        </label>
        <label className="field span-2">
          <span>File (.md, .txt or .pdf)</span>
          <input ref={fileRef} type="file" accept=".md,.txt,.pdf" required />
        </label>
        <div className="span-2">
          <button type="submit" className="button primary" disabled={busy}>
            {busy ? 'Uploading…' : 'Upload'}
          </button>
        </div>
      </form>
    </Card>
  )
}

export default function DocumentsPage() {
  const anyActive = (documents) => documents.some((d) => d.versions.some((v) => isActive(v.status)))
  const { data: documents, error, loading, refresh } = useApi(() => api.documents(), [], { poll: anyActive })

  return (
    <>
      <PageHeader title="Documents" subtitle="Regulations, internal policies and guidelines, with every uploaded version." />
      <div className="two-columns">
        <Card title="Library">
          <ErrorMessage error={error} />
          {loading && !documents && <Loading />}
          {documents?.length === 0 && <Empty>No documents yet. Upload a regulation version to start.</Empty>}
          <div className="doc-list">
            {documents?.map((doc) => (
              <div key={doc.id} className="doc">
                <div className="doc-head">
                  <strong>{doc.doc_code}</strong>
                  <span>{doc.title}</span>
                  <Badge>{doc.doc_type}</Badge>
                </div>
                <table className="table compact">
                  <thead>
                    <tr>
                      <th>Version</th>
                      <th>Effective</th>
                      <th>File</th>
                      <th>Clauses</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {doc.versions.map((version) => (
                      <tr key={version.id}>
                        <td>{version.version_label}</td>
                        <td>{version.effective_date ?? '—'}</td>
                        <td className="muted">{version.file_name}</td>
                        <td>{version.clause_count}</td>
                        <td title={version.error ?? ''}>
                          <StatusBadge status={version.status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        </Card>
        <UploadForm onUploaded={refresh} />
      </div>
    </>
  )
}
