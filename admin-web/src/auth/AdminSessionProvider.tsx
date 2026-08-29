import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'

import { AdminApi } from '../api/adminApi'
import type { AdminMe } from '../api/types'

type SessionReason = 'expired' | 'signed-out' | null

type AdminSessionContextValue = {
  api: AdminApi
  principal: AdminMe | null
  sessionReason: SessionReason
  login: (loginName: string, password: string) => Promise<void>
  logout: () => Promise<void>
  hasPermission: (permission: string) => boolean
}

const AdminSessionContext = createContext<AdminSessionContextValue | null>(null)

export function AdminSessionProvider({ children }: PropsWithChildren) {
  const [principal, setPrincipal] = useState<AdminMe | null>(null)
  const [sessionReason, setSessionReason] = useState<SessionReason>(null)
  const tokenRef = useRef<string | null>(null)
  const clearSessionRef = useRef<(reason: SessionReason) => void>(() => undefined)
  const apiRef = useRef<AdminApi | null>(null)
  if (apiRef.current === null) {
    apiRef.current = new AdminApi(
      () => tokenRef.current,
      () => clearSessionRef.current('expired'),
    )
  }
  const api = apiRef.current

  const clearSession = useCallback((reason: SessionReason) => {
    tokenRef.current = null
    setPrincipal(null)
    setSessionReason(reason)
  }, [])
  clearSessionRef.current = clearSession

  const login = useCallback(
    async (loginName: string, password: string) => {
      const created = await api.createSession(loginName, password)
      tokenRef.current = created.access_token
      try {
        const me = await api.getMe()
        setPrincipal(me)
        setSessionReason(null)
      } catch (error) {
        clearSession(null)
        throw error
      }
    },
    [api, clearSession],
  )

  const logout = useCallback(async () => {
    try {
      if (tokenRef.current !== null) await api.revokeCurrentSession()
    } finally {
      clearSession('signed-out')
    }
  }, [api, clearSession])

  useEffect(() => {
    if (principal === null) return
    const expiresAt = Date.parse(principal.expires_at)
    const delay = Math.max(0, Math.min(expiresAt - Date.now(), 2_147_000_000))
    const timer = window.setTimeout(() => clearSession('expired'), delay)
    return () => window.clearTimeout(timer)
  }, [clearSession, principal])

  const value = useMemo<AdminSessionContextValue>(
    () => ({
      api,
      principal,
      sessionReason,
      login,
      logout,
      hasPermission: (permission) => principal?.permissions.includes(permission) ?? false,
    }),
    [api, login, logout, principal, sessionReason],
  )

  return <AdminSessionContext.Provider value={value}>{children}</AdminSessionContext.Provider>
}

export function useAdminSession(): AdminSessionContextValue {
  const value = useContext(AdminSessionContext)
  if (value === null) throw new Error('useAdminSession must be used within AdminSessionProvider')
  return value
}
