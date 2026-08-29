import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { DashboardLayout } from '@/app/DashboardLayout'
import { ErrorBoundary } from '@/app/ErrorBoundary'
import { ProtectedRoute, PublicOnlyRoute } from '@/app/RouteGuards'
import { AuthProvider } from '@/auth/AuthContext'
import { ChecksPage } from '@/pages/ChecksPage'
import { DashboardHome } from '@/pages/DashboardHome'
import { LandingPage } from '@/pages/LandingPage'
import { LoginPage } from '@/pages/LoginPage'
import { NewScanPage } from '@/pages/NewScanPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { ReportPage } from '@/pages/ReportPage'
import { ScanProgressPage } from '@/pages/ScanProgressPage'
import { SignupPage } from '@/pages/SignupPage'

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/checks" element={<ChecksPage />} />

            <Route element={<PublicOnlyRoute />}>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/signup" element={<SignupPage />} />
            </Route>

            <Route element={<ProtectedRoute />}>
              <Route path="/dashboard" element={<DashboardLayout />}>
                <Route index element={<DashboardHome />} />
                <Route path="scan" element={<NewScanPage />} />
                <Route path="scan/:jobId" element={<ScanProgressPage />} />
                <Route path="report/:jobId" element={<ReportPage />} />
              </Route>
            </Route>

            <Route path="/404" element={<NotFoundPage />} />
            <Route path="*" element={<Navigate to="/404" replace />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
