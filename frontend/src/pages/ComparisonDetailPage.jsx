import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api/client.js'
import DependencyGraph from '../components/DependencyGraph.jsx'
import DiffText from '../components/DiffText.jsx'
import ReportView from '../components/ReportView.jsx'
import { Card, ChangeBadge, Empty, ErrorMessage, Loading, PageHeader, StatusBadge } from '../components/ui.jsx'
import { useApi } from '../hooks/useApi.js'
import { CHANGE_ORDER, describeDifference, isActive, splitDiff } from '../lib/changes.js'

const TABS = [
  { id: 'changes', label: 'Changes' },
  { id: 'graph', label: 'Dependency graph' },
  { id: 'reports', label: 'Impact reports' },
]

function ClauseSide({ clause, parts, label }) {
  if (!clause) return <div className="side empty-side">Not in {label}</div>
  return (
    <div className="side">
      <div className="side-meta">
        §{clause.clause_number} · p.{clause.page}
        {clause.section ? ` · ${clause.section}` : ''}
      </div>
      <DiffText parts={parts} />
    </div>
  )
}

function ChangeCard({ change, oldLabel, newLabel }) {
  const [showReport, setShowReport] = useState(false)
  const { left, right } = splitDiff(change.text_diff)
  const number = (change.new_clause ?? change.old_clause).clause_number

  return (
    <article className="change">
      <header className="change-header">
        <div className="change-title">
          <strong>Clause {number}</strong>
          <ChangeBadge type={change.change_type} />
          {change.numeric_changes.map((difference) => (
            <span key={difference.kind} className="fact-chip">
              {describeDifference(difference)}
            </span>
          ))}
        </div>
        <span className="muted small">
          similarity {Math.round(change.similarity * 100)}% · confidence {Math.round(change.confidence * 100)}%
        </span>
      </header>
      <div className="side-by-side">
        <ClauseSide clause={change.old_clause} parts={left} label={`v${oldLabel}`} />
        <ClauseSide clause={change.new_clause} parts={right} label={`v${newLabel}`} />
      </div>
      {change.report_id && (
        <div className="change-footer">
          <button type="button" className="button ghost small" onClick={() => setShowReport(!showReport)}>
            {showReport ? 'Hide impact report' : 'Show impact report'}
          </button>
        </div>
      )}
      {showReport && <InlineReport id={change.report_id} />}
    </article>
  )
}

function InlineReport({ id }) {
  const { data, error } = useApi(() => api.report(id), [id])
  if (error) return <ErrorMessage error={error} />
  return data ? <ReportView report={data} /> : <Loading />
}

function ChangesTab({ comparison, includeUnchanged }) {
  const { data: changes, error } = useApi(
    () => api.changes(comparison.id, includeUnchanged),
    [comparison.id, comparison.status, includeUnchanged],
  )
  if (error) return <ErrorMessage error={error} />
  if (!changes) return <Loading />
  if (!changes.length) return <Empty>No changes detected.</Empty>
  return changes.map((change) => (
    <ChangeCard key={change.id} change={change} oldLabel={comparison.old_version} newLabel={comparison.new_version} />
  ))
}

function GraphTab({ comparisonId }) {
  const { data, error } = useApi(() => api.graph(comparisonId), [comparisonId])
  if (error) return <ErrorMessage error={error} />
  return data ? <DependencyGraph graph={data} /> : <Loading />
}

function ReportsTab({ comparisonId }) {
  const { data, error } = useApi(() => api.reports(comparisonId), [comparisonId])
  if (error) return <ErrorMessage error={error} />
  if (!data) return <Loading />
  if (!data.length) return <Empty>No significant changes, so no impact reports.</Empty>
  return data.map((report) => <ReportView key={report.id} report={report} />)
}

export default function ComparisonDetailPage() {
  const { id } = useParams()
  const [tab, setTab] = useState('changes')
  const [includeUnchanged, setIncludeUnchanged] = useState(false)
  const { data: comparison, error } = useApi(() => api.comparison(id), [id], { poll: (c) => isActive(c.status) })

  if (error) return <ErrorMessage error={error} />
  if (!comparison) return <Loading />
  const done = comparison.status === 'done'

  return (
    <>
      <PageHeader
        title={`${comparison.doc_code}: v${comparison.old_version} → v${comparison.new_version}`}
        subtitle={comparison.doc_title}
        actions={
          <>
            <StatusBadge status={comparison.status} />
            <Link to="/comparisons" className="button ghost small">
              All comparisons
            </Link>
          </>
        }
      />
      {comparison.error && <div className="alert danger">{comparison.error}</div>}
      {!done && !comparison.error && (
        <Card>
          <p className="muted">Analysing… this page refreshes automatically.</p>
        </Card>
      )}
      {done && (
        <>
          <div className="summary-strip">
            {CHANGE_ORDER.filter((type) => comparison.counts[type]).map((type) => (
              <div key={type} className="summary-item">
                <span className="summary-count">{comparison.counts[type]}</span>
                <ChangeBadge type={type} />
              </div>
            ))}
          </div>
          <div className="tabs" role="tablist">
            {TABS.map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={tab === item.id}
                className={`tab${tab === item.id ? ' active' : ''}`}
                onClick={() => setTab(item.id)}
              >
                {item.label}
              </button>
            ))}
            {tab === 'changes' && (
              <label className="toggle">
                <input type="checkbox" checked={includeUnchanged} onChange={(e) => setIncludeUnchanged(e.target.checked)} />
                Show unchanged clauses
              </label>
            )}
          </div>
          {tab === 'changes' && <ChangesTab comparison={comparison} includeUnchanged={includeUnchanged} />}
          {tab === 'graph' && (
            <Card>
              <GraphTab comparisonId={comparison.id} />
            </Card>
          )}
          {tab === 'reports' && <ReportsTab comparisonId={comparison.id} />}
        </>
      )}
    </>
  )
}
