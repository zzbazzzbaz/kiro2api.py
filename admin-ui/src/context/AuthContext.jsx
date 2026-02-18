import { createContext, useContext, useState, useCallback } from 'react'
import { setAuth, clearAuth, isLoggedIn as checkLoggedIn, getBaseUrl } from '@/api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [loggedIn, setLoggedIn] = useState(checkLoggedIn())

  const login = useCallback((baseUrl, adminKey) => {
    setAuth(baseUrl, adminKey)
    setLoggedIn(true)
  }, [])

  const logout = useCallback(() => {
    clearAuth()
    setLoggedIn(false)
  }, [])

  return (
    <AuthContext.Provider value={{ loggedIn, login, logout, getBaseUrl }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
