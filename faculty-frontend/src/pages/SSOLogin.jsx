import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import LoadingSpinner from '../components/LoadingSpinner'
import Alert from '../components/Alert'
import api from '../services/api'
import { useAuth } from '../context/AuthContext'

export default function SSOLogin() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { login } = useAuth()
  const [error, setError] = useState(null)

  useEffect(() => {
    const token = searchParams.get('sso_token')
    if (!token) {
      setError('Missing SSO token')
      return
    }

    let isMounted = true

    async function run() {
      try {
        const resp = await api.get('/auth/sso-login/', {
          params: { sso_token: token }
        })

        if (!isMounted) return
        await login(resp.data)
        navigate('/', { replace: true })
      } catch (err) {
        console.error('SSO login failed:', err)
        const message = err.response?.data?.detail || 'SSO login failed'
        if (isMounted) setError(message)
      }
    }

    run()
    return () => {
      isMounted = false
    }
  }, [searchParams, login, navigate])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center max-w-md w-full px-4">
        {error ? (
          <Alert variant="error" onClose={() => setError(null)}>
            {error}
          </Alert>
        ) : (
          <>
            <LoadingSpinner size="lg" />
            <p className="mt-4 text-gray-600">Signing you in…</p>
          </>
        )}
      </div>
    </div>
  )
}
