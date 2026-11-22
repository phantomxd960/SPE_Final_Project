import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import { api, getToken, setToken, setUnauthorizedHandler } from '../api/client.js'

const AuthContext = createContext(null)

function readUser() {
  // The token alone is enough to render the app; /api/auth/me confirms it on load.
  return getToken() ? { email: '' } : null
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(readUser)

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(logout)
    if (getToken()) {
      api.me().then(setUser).catch(() => logout())
    }
  }, [logout])

  const login = useCallback(async (email, password) => {
    const { access_token: token } = await api.login(email, password)
    setToken(token)
    setUser(await api.me())
  }, [])

  const value = useMemo(() => ({ user, login, logout }), [user, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  return useContext(AuthContext)
}
