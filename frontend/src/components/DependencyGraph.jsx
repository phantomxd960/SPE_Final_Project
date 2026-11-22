import { layoutGraph, NODE_HEIGHT, NODE_WIDTH } from '../lib/graphLayout.js'
import { Empty } from './ui.jsx'

const TYPE_LABELS = {
  reg_clause: 'Regulation clause',
  policy_clause: 'Policy clause',
  policy: 'Policy',
  process: 'Process',
  control: 'Control',
}

// GRF-7: changed clauses on the left, everything that depends on them to the right.
// Solid edges are confirmed references; dashed edges are inferred by similarity.
export default function DependencyGraph({ graph }) {
  if (!graph?.nodes?.length) {
    return <Empty>No dependencies found for the changed clauses.</Empty>
  }
  const { width, height, nodes, edges } = layoutGraph(graph)

  return (
    <div className="graph">
      <div className="graph-legend">
        {Object.entries(TYPE_LABELS).map(([type, label]) => (
          <span key={type} className={`legend-item node-${type}`}>
            {label}
          </span>
        ))}
        <span className="legend-item edge-confirmed">confirmed</span>
        <span className="legend-item edge-inferred">inferred</span>
      </div>
      <div className="graph-scroll">
        <svg width={width} height={height} role="img" aria-label="Compliance dependency graph">
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" className="graph-arrow" />
            </marker>
          </defs>
          {edges.map((edge) => {
            const mid = (edge.x1 + edge.x2) / 2
            return (
              <path
                key={`${edge.source}-${edge.target}-${edge.rel_type}`}
                d={`M${edge.x1},${edge.y1} C${mid},${edge.y1} ${mid},${edge.y2} ${edge.x2},${edge.y2}`}
                className={`graph-edge ${edge.status}`}
                markerEnd="url(#arrow)"
              >
                <title>{`${edge.rel_type} (${edge.status}, ${Math.round(edge.confidence * 100)}%)`}</title>
              </path>
            )
          })}
          {nodes.map((node) => (
            <g key={node.id} transform={`translate(${node.x},${node.y})`} className={`graph-node node-${node.type}`}>
              <rect width={NODE_WIDTH} height={NODE_HEIGHT} rx="8" className={node.change_type ? 'changed' : ''} />
              <text x="12" y="18" className="graph-node-type">
                {TYPE_LABELS[node.type]}
                {node.change_type ? ` · ${node.change_type.replace('_', ' ')}` : ''}
              </text>
              <text x="12" y="34" className="graph-node-label">
                {node.label.length > 26 ? `${node.label.slice(0, 25)}…` : node.label}
              </text>
              <title>{node.label}</title>
            </g>
          ))}
        </svg>
      </div>
    </div>
  )
}
