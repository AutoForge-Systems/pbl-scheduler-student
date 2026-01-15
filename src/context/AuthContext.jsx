import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import api from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadUser = useCallback(async () => {
    const token = localStorage.getItem('access_token')
    
    if (!token) {
      setUser(null)
      setError(null)
      setIsLoading(false)
      return
    }

    try {
      const response = await api.get('/users/me/')
      setUser(response.data)
      setError(null)
    } catch (err) {
      console.error('Failed to load user:', err)
      // Clear invalid tokens
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      setUser(null)
      setError('Session expired. Please login again.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadUser()
  }, [loadUser])

  // If an API call detects 401 and clears tokens, bring auth state in sync.
  useEffect(() => {
    function onLogout() {
      setUser(null)
      setError(null)
      setIsLoading(false)
    }
    window.addEventListener('auth:logout', onLogout)
    return () => window.removeEventListener('auth:logout', onLogout)
  }, [])

  const login = useCallback(async (tokens) => {
    localStorage.setItem('access_token', tokens.access)
    localStorage.setItem('refresh_token', tokens.refresh)
    // Set user directly from tokens if available
    if (tokens.user) {
      setUser(tokens.user)
      setError(null)
      setIsLoading(false)
    } else {
      setIsLoading(true)
      await loadUser()
    }
  }, [loadUser])

  const logout = useCallback(() => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    setUser(null)
    setError(null)
    setIsLoading(false)
  }, [])

  const value = {
    user,
    isAuthenticated: !!user,
    isLoading,
    error,
    login,
    logout,
    refreshUser: loadUser
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
