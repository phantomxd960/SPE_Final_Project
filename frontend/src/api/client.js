// Thin fetch wrapper: adds the bearer token, parses the API's uniform error shape
// {code, message, request_id}, and signs out on 401.

const TOKEN_KEY = 'regulationdiff.token'

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    // storage unavailable (private mode): the session simply will not persist
  }
}

export class ApiError extends Error {
  constructor(status, body) {
    super(body?.message || `Request failed (${status})`)
    this.status = status
    this.code = body?.code
    this.requestId = body?.request_id
  }
}

let onUnauthorized = () => {}
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler
}

async function request(path, { method = 'GET', json, form, raw = false } = {}) {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  let body
  if (json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(json)
  } else if (form) {
    body = form
  }

  const response = await fetch(path, { method, headers, body })
  if (response.status === 401 && token) onUnauthorized()
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null)
    throw new ApiError(response.status, errorBody)
  }
  if (raw) return response
  return response.status === 204 ? null : response.json()
}

const query = (params) => {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
  return entries.length ? `?${new URLSearchParams(entries)}` : ''
}

export const api = {
  version: () => request('/api/version'),
  login: (email, password) => request('/api/auth/login', { method: 'POST', json: { email, password } }),
  me: () => request('/api/auth/me'),

  documents: () => request('/api/documents'),
  upload: (formData) => request('/api/documents', { method: 'POST', form: formData }),
  clause: (id) => request(`/api/clauses/${id}`),

  comparisons: () => request('/api/comparisons'),
  createComparison: (oldVersionId, newVersionId) =>
    request('/api/comparisons', {
      method: 'POST',
      json: { old_version_id: oldVersionId, new_version_id: newVersionId },
    }),
  comparison: (id) => request(`/api/comparisons/${id}`),
  changes: (id, includeUnchanged = false) =>
    request(`/api/comparisons/${id}/changes${query({ include_unchanged: includeUnchanged })}`),
  graph: (id) => request(`/api/graph/${id}`),
  reports: (id) => request(`/api/comparisons/${id}/reports`),
  report: (id) => request(`/api/reports/${id}`),
  downloadReport: (id) => request(`/api/reports/${id}?download=true`, { raw: true }),

  search: (params) => request(`/api/search${query(params)}`),
}
