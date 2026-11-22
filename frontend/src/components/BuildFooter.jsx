import { useEffect, useState } from 'react'

import { api } from '../api/client.js'

// UI-6 / DEV-8: shows which build is running, so a refresh after a deploy proves the update.
const UI_BUILD = import.meta.env.VITE_BUILD_NUMBER || 'dev'
const UI_COMMIT = import.meta.env.VITE_GIT_COMMIT || 'local'

export default function BuildFooter() {
  const [backend, setBackend] = useState(null)

  useEffect(() => {
    api.version().then(setBackend).catch(() => setBackend(null))
  }, [])

  return (
    <footer className="footer">
      <span>
        UI build <strong>#{UI_BUILD}</strong> · {UI_COMMIT.slice(0, 7)}
      </span>
      <span>
        API build <strong>#{backend?.build_number ?? '…'}</strong> · {backend?.git_commit?.slice(0, 7) ?? '…'}
        {backend?.build_time && backend.build_time !== 'unknown' ? ` · built ${backend.build_time}` : ''}
      </span>
    </footer>
  )
}
