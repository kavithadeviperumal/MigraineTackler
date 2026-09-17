'use client'

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'

import {
  type AuthUser,
  clearAuth,
  getAccessToken,
  getRefreshToken,
  getStoredUser,
  setTokens,
  storeUser,
} from '@/lib/auth'

interface AuthContextValue {
  user: AuthUser | null
  isAuthenticated: boolean
  login: (user: AuthUser, accessToken: string, refreshToken: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)

  // Hydrate from localStorage after mount (avoids SSR mismatch)
  useEffect(() => {
    const stored = getStoredUser()
    const token = getAccessToken()
    if (stored && token) setUser(stored)
  }, [])

  const login = useCallback(
    (user: AuthUser, accessToken: string, refreshToken: string) => {
      setTokens(accessToken, refreshToken)
      storeUser(user)
      setUser(user)
    },
    [],
  )

  const logout = useCallback(() => {
    const rt = getRefreshToken()
    clearAuth()
    setUser(null)
    // Best-effort server-side revoke — don't block on it
    if (rt) {
      fetch(`${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}/auth/logout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: rt }),
      }).catch(() => {})
    }
  }, [])

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: !!user, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}