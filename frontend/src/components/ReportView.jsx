import { useState } from 'react'

import { api } from '../api/client.js'
import { describeDifference } from '../lib/changes.js'
import ClauseDialog from './ClauseDialog.jsx'
import { Badge, ChangeBadge, RelationBadge } from './ui.jsx'

function CitationList({ ids, evidence, onOpen }) {
  return (
    <span className="citations">
      {ids.map((id) => {
        const item = evidence[id]
        return (
          <button
            key={id}
            type="button"
            className="citation"
            title={item ? `${item.doc_code} v${item.version_label} §${item.clause_number}, p.${item.page}` : id}
            onClick={() => item?.clause_id && onOpen(item.clause_id)}
          >
            {id}
          </button>
        )
      })}
    </span>
  )
}

// IMP-1 to IMP-7: confirmed change and inferred impacts kept apart, every statement cited.
export default function ReportView({ report }) {
  const [openClause, setOpenClause] = useState(null)
  const evidence = Object.fromEntries(report.evidence.map((item) => [item.id, item]))
  const confirmed = report.confirmed
  const Citations = ({ ids }) => <CitationList ids={ids} evidence={evidence} onOpen={setOpenClause} />

  async function download() {
    const response = await api.downloadReport(report.id)
    const url = URL.createObjectURL(await response.blob())
    const link = Object.assign(document.createElement('a'), { href: url, download: `impact-report-${report.id}.json` })
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <article className="report">
      <header className="report-header">
        <div className="report-title">
          <h3>
            Clause {confirmed.clause} <ChangeBadge type={confirmed.change_type} />
          </h3>
          <span className="muted">
            {confirmed.old_version ? `v${confirmed.old_version}` : '—'} → {confirmed.new_version ? `v${confirmed.new_version}` : '—'} ·
            model {report.model}
          </span>
        </div>
        <div className="report-actions">
          {report.verified ? (
            <Badge tone="success" title="Every citation was checked against the supplied evidence">
              verified
            </Badge>
          ) : (
            <Badge tone="danger" title={confirmed.validation_errors?.join('\n')}>
              unverified
            </Badge>
          )}
          <button type="button" className="button ghost small" onClick={download}>
            Download JSON
          </button>
        </div>
      </header>

      <section className="report-section">
        <h4>Confirmed change</h4>
        <p>
          {report.summary} <Citations ids={confirmed.evidence_ids ?? []} />
        </p>
        {confirmed.differences?.length > 0 && (
          <ul className="facts">
            {confirmed.differences.map((difference) => (
              <li key={difference.kind}>{describeDifference(difference)}</li>
            ))}
          </ul>
        )}
      </section>

      <section className="report-section">
        <h4>Affected policies, processes and controls</h4>
        {report.affected.length === 0 && <p className="muted">No dependent items were found in the graph.</p>}
        <ul className="affected">
          {report.affected.map((item) => (
            <li key={item.id}>
              <div className="affected-head">
                <strong>{item.label}</strong>
                <Badge>{item.kind}</Badge>
                <RelationBadge relation={item.relation} />
              </div>
              {item.reason && (
                <p>
                  {item.reason} <Citations ids={item.evidence_ids} />
                </p>
              )}
              {item.path?.length > 1 && <p className="path">{item.path.map((p) => p.split(':')[1]).join(' → ')}</p>}
            </li>
          ))}
        </ul>
      </section>

      {report.impacts.length > 0 && (
        <section className="report-section">
          <h4>Potential impact (inferred)</h4>
          <ul>
            {report.impacts.map((impact, index) => (
              <li key={index}>
                {impact.statement} <Citations ids={impact.evidence_ids} />
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="report-section">
        <h4>Recommended actions</h4>
        <ol>
          {report.actions.map((action, index) => (
            <li key={index}>
              {action.action} <Citations ids={action.evidence_ids} />
            </li>
          ))}
        </ol>
      </section>

      <details className="report-section">
        <summary>Evidence ({report.evidence.length})</summary>
        <ul className="evidence">
          {report.evidence.map((item) => (
            <li key={item.id}>
              <button type="button" className="citation" onClick={() => setOpenClause(item.clause_id)}>
                {item.id}
              </button>{' '}
              <span className="muted">
                {item.doc_code} v{item.version_label} §{item.clause_number} · p.{item.page} · {item.role.replace('_', ' ')}
              </span>
              <p>{item.text}</p>
            </li>
          ))}
        </ul>
      </details>

      <p className="disclaimer">{confirmed.disclaimer}</p>
      {openClause && <ClauseDialog clauseId={openClause} onClose={() => setOpenClause(null)} />}
    </article>
  )
}
