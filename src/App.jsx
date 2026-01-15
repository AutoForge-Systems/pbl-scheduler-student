import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import Layout from './components/Layout'
import AuthCallback from './pages/AuthCallback'
import SSOLogin from './pages/SSOLogin'
import Dashboard from './pages/Dashboard'
import AvailableSlots from './pages/AvailableSlots'
import MyBooking from './pages/MyBooking'
import LoadingSpinner from './components/LoadingSpinner'

// Dev-only lazy import (tree-shaken in production build)
const DevLogin = import.meta.env.DEV 
  ? lazy(() => import('./pages/DevLogin'))
  : null

function App() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <Routes>
      <Route path="/sso-login" element={<SSOLogin />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      
      {/* Dev-only route - only available when import.meta.env.DEV is true */}
      {import.meta.env.DEV && DevLogin && (
        <Route 
          path="/dev-login" 
          element={
            <Suspense fallback={<LoadingSpinner size="lg" />}>
              <DevLogin />
            </Suspense>
          } 
        />
      )}
      
      {isAuthenticated ? (
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="slots" element={<AvailableSlots />} />
          <Route path="booking" element={<MyBooking />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      ) : (
        <Route path="*" element={<AuthRequired />} />
      )}
    </Routes>
  )
}

function AuthRequired() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-gray-900 mb-4">
          Authentication Required
        </h1>
        <p className="text-gray-600 mb-4">
          Please access this application through the PBL platform.
        </p>
        <p className="text-sm text-gray-500">
          You will be automatically authenticated via SSO.
        </p>
        
        {/* Dev-only login link */}
        {import.meta.env.DEV && (
          <div className="mt-8 pt-6 border-t border-gray-200">
            <p className="text-xs text-yellow-600 mb-2">Development Mode</p>
            <a
              href="/dev-login"
              className="inline-flex items-center gap-2 px-4 py-2 bg-yellow-100 hover:bg-yellow-200 text-yellow-800 rounded-lg text-sm font-medium transition-colors"
            >
              🔧 Dev Login
            </a>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
