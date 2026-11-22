// Small presentational building blocks shared by the pages.

import { changeLabel, changeTone, STATUS_TONES } from '../lib/changes.js'

export function Badge({ tone = 'neutral', children, title }) {
  return (
    <span className={`badge ${tone}`} title={title}>
      {children}
    </span>
  )
}

export function StatusBadge({ status }) {
  return <Badge tone={STATUS_TONES[status] ?? 'neutral'}>{status}</Badge>
}

export function ChangeBadge({ type }) {
  return <Badge tone={changeTone(type)}>{changeLabel(type)}</Badge>
}

export function RelationBadge({ relation }) {
  return (
    <Badge
      tone={relation === 'confirmed' ? 'success' : 'warning'}
      title={relation === 'confirmed' ? 'Explicit reference in the policy text' : 'Suggested by semantic similarity'}
    >
      {relation}
    </Badge>
  )
}

export function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  )
}

export function Card({ title, actions, children, className = '' }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="card-header">
          {title && <h2>{title}</h2>}
          {actions}
        </div>
      )}
      {children}
    </section>
  )
}

export function ErrorMessage({ error }) {
  if (!error) return null
  return (
    <div className="alert danger" role="alert">
      {error.message}
      {error.requestId && <span className="muted"> (request {error.requestId.slice(0, 8)})</span>}
    </div>
  )
}

export function Empty({ children }) {
  return <p className="empty">{children}</p>
}

export function Loading() {
  return <p className="empty">Loading…</p>
}
