// Layered layout for the dependency graph: impact flows left to right,
// regulation clause -> policy clause -> policy -> process / control.

export const COLUMNS = ['reg_clause', 'policy_clause', 'policy', 'process', 'control']
const COLUMN_OF = { reg_clause: 0, policy_clause: 1, policy: 2, process: 3, control: 3 }

export const NODE_WIDTH = 190
export const NODE_HEIGHT = 44
const COLUMN_GAP = 70
const ROW_GAP = 18
const PADDING = 16

export function layoutGraph(graph) {
  const columns = [[], [], [], []]
  const sorted = [...graph.nodes].sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true }))
  for (const node of sorted) columns[COLUMN_OF[node.type] ?? 3].push(node)

  const rows = Math.max(1, ...columns.map((c) => c.length))
  const height = PADDING * 2 + rows * NODE_HEIGHT + (rows - 1) * ROW_GAP
  const positions = {}
  columns.forEach((column, index) => {
    const columnHeight = column.length * NODE_HEIGHT + Math.max(0, column.length - 1) * ROW_GAP
    const top = (height - columnHeight) / 2
    column.forEach((node, row) => {
      positions[node.id] = {
        x: PADDING + index * (NODE_WIDTH + COLUMN_GAP),
        y: top + row * (NODE_HEIGHT + ROW_GAP),
      }
    })
  })

  const usedColumns = columns.filter((c) => c.length).length || 1
  const width = PADDING * 2 + usedColumns * NODE_WIDTH + (usedColumns - 1) * COLUMN_GAP
  const nodes = sorted.map((node) => ({ ...node, ...positions[node.id] }))

  // Edges are stored dependent -> dependency; draw them in the direction impact flows.
  const edges = graph.edges
    .filter((edge) => positions[edge.source] && positions[edge.target])
    .map((edge) => {
      const from = positions[edge.target]
      const to = positions[edge.source]
      return {
        ...edge,
        x1: from.x + NODE_WIDTH,
        y1: from.y + NODE_HEIGHT / 2,
        x2: to.x,
        y2: to.y + NODE_HEIGHT / 2,
      }
    })

  return { width: Math.max(width, 4 * NODE_WIDTH + 3 * COLUMN_GAP + PADDING * 2), height, nodes, edges }
}
