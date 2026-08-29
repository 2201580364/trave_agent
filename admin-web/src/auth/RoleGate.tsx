import type { PropsWithChildren } from 'react'
import { Result } from 'antd'

import { useAdminSession } from './AdminSessionProvider'

type RoleGateProps = PropsWithChildren<{
  permission: string
  fallback?: React.ReactNode
}>

export function RoleGate({ permission, fallback, children }: RoleGateProps) {
  const { hasPermission } = useAdminSession()
  if (!hasPermission(permission)) {
    return (
      fallback ?? (
        <Result
          status="403"
          title="没有访问权限"
          subTitle={`此页面需要服务端权限：${permission}`}
        />
      )
    )
  }
  return children
}
