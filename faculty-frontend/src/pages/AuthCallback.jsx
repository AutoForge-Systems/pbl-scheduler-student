import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import LoadingSpinner from '../components/LoadingSpinner'

export default function AuthCallback() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { login } = useAuth()

  useEffect(() => {
    const access = searchParams.get('access')
    const refresh = searchParams.get('refresh')

    if (access && refresh) {
      login({ access, refresh })
      navigate('/', { replace: true })
    } else {
      navigate('/', { replace: true })
    }
  }, [searchParams, login, navigate])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <LoadingSpinner size="lg" />
        <p className="mt-4 text-gray-600">Authenticating...</p>
      </div>
    </div>
  )
}
