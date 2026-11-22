// Presentation helpers for change types, statuses and word diffs. Pure functions, unit-tested.

export const CHANGE_TYPES = {
  substantially_changed: { label: 'Substantially changed', tone: 'danger' },
  added: { label: 'Added', tone: 'success' },
  deleted: { label: 'Deleted', tone: 'danger-soft' },
  modified: { label: 'Modified', tone: 'warning' },
  renumbered: { label: 'Renumbered', tone: 'info' },
  semantically_equivalent: { label: 'Equivalent', tone: 'neutral' },
  unchanged: { label: 'Unchanged', tone: 'neutral' },
}

export const CHANGE_ORDER = Object.keys(CHANGE_TYPES)

export function changeLabel(type) {
  return CHANGE_TYPES[type]?.label ?? type
}

export function changeTone(type) {
  return CHANGE_TYPES[type]?.tone ?? 'neutral'
}

export const STATUS_TONES = {
  queued: 'neutral',
  processing: 'info',
  running: 'info',
  ready: 'success',
  done: 'success',
  failed: 'danger',
}

export function isActive(status) {
  return status === 'queued' || status === 'processing' || status === 'running'
}

// Split a word diff [[op, text], ...] into what each side of a side-by-side view shows.
export function splitDiff(ops) {
  const left = []
  const right = []
  for (const [op, text] of ops) {
    if (op === 'equal') {
      left.push({ op, text })
      right.push({ op, text })
    } else if (op === 'delete') {
      left.push({ op, text })
    } else if (op === 'insert') {
      right.push({ op, text })
    }
  }
  return { left, right }
}

export function describeDifference({ kind, old, new: added }) {
  const before = old.length ? old.join(', ') : 'none'
  const after = added.length ? added.join(', ') : 'none'
  return `${kind}: ${before} → ${after}`
}
