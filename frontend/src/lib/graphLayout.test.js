import { describe, expect, it } from 'vitest'

import { layoutGraph, NODE_WIDTH } from './graphLayout.js'

const graph = {
  nodes: [
    { id: 'reg_clause:REG001#4.2.1', type: 'reg_clause', label: 'REG001 §4.2.1' },
    { id: 'policy_clause:POL-TM#2.1', type: 'policy_clause', label: 'POL-TM §2.1' },
    { id: 'policy:POL-TM', type: 'policy', label: 'Transaction Monitoring Policy' },
    { id: 'process:Transaction Monitoring', type: 'process', label: 'Transaction Monitoring' },
  ],
  edges: [
    { source: 'policy_clause:POL-TM#2.1', target: 'reg_clause:REG001#4.2.1', rel_type: 'REFERENCES', status: 'confirmed' },
    { source: 'policy:POL-TM', target: 'policy_clause:POL-TM#2.1', rel_type: 'DEPENDS_ON', status: 'confirmed' },
    { source: 'ghost', target: 'policy:POL-TM', rel_type: 'DEPENDS_ON', status: 'confirmed' },
  ],
}

describe('layoutGraph', () => {
  it('places each node type in its own column, left to right', () => {
    const { nodes } = layoutGraph(graph)
    const x = Object.fromEntries(nodes.map((n) => [n.type, n.x]))
    expect(x.reg_clause).toBeLessThan(x.policy_clause)
    expect(x.policy_clause).toBeLessThan(x.policy)
    expect(x.policy).toBeLessThan(x.process)
  })

  it('draws edges in the direction impact flows and drops dangling ones', () => {
    const { edges, nodes } = layoutGraph(graph)
    expect(edges).toHaveLength(2)
    const regulation = nodes.find((n) => n.type === 'reg_clause')
    expect(edges[0].x1).toBe(regulation.x + NODE_WIDTH)
  })
})
