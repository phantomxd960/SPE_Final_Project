// Renders one side of a word diff: deletions on the old side, insertions on the new side.
export default function DiffText({ parts }) {
  return (
    <p className="clause-text">
      {parts.map((part, index) =>
        part.op === 'equal' ? (
          <span key={index}>{part.text}</span>
        ) : (
          <mark key={index} className={part.op === 'delete' ? 'diff-del' : 'diff-ins'}>
            {part.text}
          </mark>
        ),
      )}
    </p>
  )
}
