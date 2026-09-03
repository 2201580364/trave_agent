import { Spin } from 'antd'
import { lazy, Suspense } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { AdminSessionGuard } from '../auth/AdminSessionGuard'
import { AdminSessionProvider } from '../auth/AdminSessionProvider'
import { RoleGate } from '../auth/RoleGate'
import { AdminLayout } from '../layout/AdminLayout'

const AdminActorsPage = lazy(() =>
  import('../pages/AdminActorsPage').then((module) => ({ default: module.AdminActorsPage })),
)
const AuditEventsPage = lazy(() =>
  import('../pages/AuditEventsPage').then((module) => ({ default: module.AuditEventsPage })),
)
const HomePage = lazy(() =>
  import('../pages/HomePage').then((module) => ({ default: module.HomePage })),
)
const LoginPage = lazy(() =>
  import('../pages/LoginPage').then((module) => ({ default: module.LoginPage })),
)
const NotFoundPage = lazy(() =>
  import('../pages/NotFoundPage').then((module) => ({ default: module.NotFoundPage })),
)
const ReviewQueuePage = lazy(() =>
  import('../pages/ReviewQueuePage').then((module) => ({ default: module.ReviewQueuePage })),
)
const CandidatesPage = lazy(() =>
  import('../pages/CandidatesPage').then((module) => ({ default: module.CandidatesPage })),
)
const PublicationsPage = lazy(() => import('../pages/PublicationsPage').then((module) => ({ default: module.PublicationsPage })))
const RevisionDetailsPage = lazy(() =>
  import('../pages/RevisionDetailsPage').then((module) => ({ default: module.RevisionDetailsPage })),
)
const HolidayCalendarsPage = lazy(() =>
  import('../pages/HolidayCalendarsPage').then((module) => ({ default: module.HolidayCalendarsPage })),
)

export function App() {
  return (
    <BrowserRouter>
      <AdminSessionProvider>
        <Suspense
          fallback={
            <div className="route-loading" aria-label="页面加载中">
              <Spin size="large" />
            </div>
          }
        >
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<AdminSessionGuard />}>
              <Route element={<AdminLayout />}>
                <Route index element={<HomePage />} />
                <Route
                  path="administrators"
                  element={
                    <RoleGate permission="admin:actor:read">
                      <AdminActorsPage />
                    </RoleGate>
                  }
                />
                <Route
                  path="audit"
                  element={
                    <RoleGate permission="admin:audit:read">
                      <AuditEventsPage />
                    </RoleGate>
                  }
                />
                <Route
                  path="review"
                  element={
                    <RoleGate permission="place:review:read">
                      <ReviewQueuePage />
                    </RoleGate>
                  }
                />
                <Route
                  path="candidates"
                  element={
                    <RoleGate permission="place:candidate:read">
                      <CandidatesPage />
                    </RoleGate>
                  }
                />
                <Route path="publications" element={<RoleGate permission="place:publication:check"><PublicationsPage /></RoleGate>} />
                <Route path="holiday-calendars" element={<RoleGate permission="holiday:calendar:read"><HolidayCalendarsPage /></RoleGate>} />
                <Route
                  path="candidates/:revisionId"
                  element={
                    <RoleGate permission="place:candidate:read">
                      <RevisionDetailsPage />
                    </RoleGate>
                  }
                />
                <Route path="*" element={<NotFoundPage />} />
              </Route>
            </Route>
          </Routes>
        </Suspense>
      </AdminSessionProvider>
    </BrowserRouter>
  )
}
