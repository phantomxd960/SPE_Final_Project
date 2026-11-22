import { useEffect, useRef } from 'react'

import { api } from '../api/client.js'
import { useApi } from '../hooks/useApi.js'
import { ErrorMessage, Loading } from './ui.jsx'

// UI-4: opening a citation shows the stored source clause.
export default function ClauseDialog({ clauseId, onClose }) {
  const dialogRef = useRef(null)
  const { data: clause, error, loading } = useApi(() => api.clause(clauseId), [clauseId])

  useEffect(() => {
    const dialog = dialogRef.current
    dialog?.showModal()
    return () => dialog?.close()
  }, [])

  return (
    <dialog ref={dialogRef} className="dialog" onClose={onClose} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="dialog-body">
        <div className="card-header">
          <h2>Source clause</h2>
          <button type="button" className="button ghost small" onClick={onClose}>
            Close
          </button>
        </div>
        <ErrorMessage error={error} />
        {loading && <Loading />}
        {clause && (
          <>
            <p className="muted">
              {clause.doc_code} · {clause.doc_title} · version {clause.version_label} · clause {clause.clause_number} ·
              page {clause.page}
              {clause.section ? ` · ${clause.section}` : ''}
            </p>
            <blockquote className="quote">{clause.text}</blockquote>
          </>
        )}
      </div>
    </dialog>
  )
}
