import { describe, expect, it } from 'vitest'

import { changeLabel, describeDifference, isActive, splitDiff } from './changes.js'

describe('splitDiff', () => {
  it('puts deletions on the left and insertions on the right', () => {
    const { left, right } = splitDiff([
      ['equal', 'EUR '],
      ['delete', '10,000'],
      ['insert', '5,000'],
      ['equal', ' or more'],
    ])
    expect(left.map((p) => p.text).join('')).toBe('EUR 10,000 or more')
    expect(right.map((p) => p.text).join('')).toBe('EUR 5,000 or more')
    expect(left.find((p) => p.op === 'delete').text).toBe('10,000')
  })
})

describe('labels', () => {
  it('maps known change types and keeps unknown ones', () => {
    expect(changeLabel('substantially_changed')).toBe('Substantially changed')
    expect(changeLabel('mystery')).toBe('mystery')
  })

  it('describes a deterministic difference', () => {
    expect(describeDifference({ kind: 'amount', old: ['EUR 10,000'], new: ['EUR 5,000'] })).toBe(
      'amount: EUR 10,000 → EUR 5,000',
    )
  })

  it('knows which statuses are still in progress', () => {
    expect(isActive('running')).toBe(true)
    expect(isActive('done')).toBe(false)
  })
})
