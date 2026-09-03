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
import { App as AntApp } from 'antd'

import { AdminApi } from '../api/adminApi'
import { adminErrorMessage } from '../api/errorMessages'
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
  const { notification } = AntApp.useApp()
  const [principal, setPrincipal] = useState<AdminMe | null>(null)
  const [sessionReason, setSessionReason] = useState<SessionReason>(null)
  const tokenRef = useRef<string | null>(null)
  const clearSessionRef = useRef<(reason: SessionReason) => void>(() => undefined)
  const requestErrorRef = useRef<(error: unknown) => void>(() => undefined)
  const apiRef = useRef<AdminApi | null>(null)
  if (apiRef.current === null) {
    apiRef.current = new AdminApi(
      () => tokenRef.current,
      () => clearSessionRef.current('expired'),
      (error) => requestErrorRef.current(error),
    )
  }
  const api = apiRef.current

  const clearSession = useCallback((reason: SessionReason) => {
    tokenRef.current = null
    setPrincipal(null)
    setSessionReason(reason)
  }, [])
  clearSessionRef.current = clearSession
  requestErrorRef.current = (error) => {
    const status = typeof error === 'object' && error !== null && 'status' in error
      ? Number(error.status)
      : 0
    const constraint = status === 400 || status === 403 || status === 409 || status === 422
    const open = constraint ? notification.warning : notification.error
    open({
      key: 'admin-api-error',
      message: constraint ? '操作受限' : status === 401 ? '登录状态已失效' : '操作未完成',
      description: adminErrorMessage(error),
      placement: 'topRight',
      duration: 6,
    })
  }

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
