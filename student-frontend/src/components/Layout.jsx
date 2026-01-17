import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Calendar, Home, BookOpen, LogOut, User, ExternalLink } from 'lucide-react'
import logoUrl from '../../../faculty-frontend/logo.png'

const DEFAULT_PBL_APP_URL = 'https://pbl-form.vercel.app'

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  const handleBackToPbl = () => {
    const stored = (localStorage.getItem('pbl_return_url') || '').trim()
    const fallback = (import.meta.env.VITE_PBL_APP_URL || '').trim() || DEFAULT_PBL_APP_URL
    const url = stored || fallback
    window.location.assign(url)
  }

  const navItems = [
    { to: '/', icon: Home, label: 'Dashboard' },
    { to: '/slots', icon: Calendar, label: 'Available Slots' },
    { to: '/booking', icon: BookOpen, label: 'My Booking' }
  ]

  const pageTitle = (() => {
    const path = location.pathname
    const match = navItems
      .slice()
      .sort((a, b) => b.to.length - a.to.length)
      .find((i) => (i.to === '/' ? path === '/' : path.startsWith(i.to)))
    return match?.label || 'Student Panel'
  })()

  return (
    <div className="h-screen bg-gray-50 flex flex-col overflow-x-hidden">
      {/* Sticky Top Bar */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-14 sm:h-16">
            <div className="flex items-center gap-2 min-w-0">
              <img
                src={logoUrl}
                alt="PBL Scheduler"
                className="w-8 h-8 object-contain flex-shrink-0"
              />
              <div className="min-w-0">
                {/* Mobile: page title */}
                <div className="sm:hidden">
                  <div className="text-sm font-semibold text-gray-900 truncate">{pageTitle}</div>
                  <div className="text-xs text-gray-500 truncate">{user?.name}</div>
                </div>

                {/* Desktop: app title */}
                <div className="hidden sm:block">
                  <div className="text-xl font-bold text-gray-900">Graphic Era Hill University</div>
                  <div className="text-xs text-gray-500">Student Panel</div>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <div className="hidden sm:flex items-center space-x-2 text-gray-700">
                <User className="w-5 h-5" />
                <span className="text-sm font-medium truncate max-w-[14rem]">{user?.name}</span>
              </div>
              <button
                onClick={handleBackToPbl}
                className="inline-flex items-center justify-center gap-2 rounded-lg px-3 text-gray-600 hover:text-gray-900 hover:bg-gray-100 h-11"
                aria-label="Back to PBL"
                title="Back to PBL"
              >
                <ExternalLink className="w-4 h-4" />
                <span className="hidden sm:inline text-sm">Back to PBL</span>
              </button>
              <button
                onClick={handleLogout}
                className="inline-flex items-center justify-center gap-2 rounded-lg px-3 text-gray-600 hover:text-gray-900 hover:bg-gray-100 h-11"
                aria-label="Logout"
              >
                <LogOut className="w-4 h-4" />
                <span className="hidden sm:inline text-sm">Logout</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        {/* Desktop Sidebar */}
        <nav className="hidden lg:block w-64 bg-white border-r border-gray-200">
          <div className="h-full overflow-y-auto p-4 space-y-1">
            {navItems.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `flex items-center space-x-3 px-4 py-3 rounded-lg transition-colors ${
                    isActive
                      ? 'bg-primary-50 text-primary-700'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`
                }
              >
                <Icon className="w-5 h-5" />
                <span className="font-medium">{label}</span>
              </NavLink>
            ))}
          </div>
        </nav>

        {/* Main Content */}
        <main className="flex-1 min-h-0 overflow-y-auto px-4 py-4 sm:px-6 sm:py-6 lg:p-8 pb-24 lg:pb-8">
          <div className="max-w-5xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>

      {/* Mobile Bottom Navigation */}
      <nav className="lg:hidden fixed bottom-0 left-0 right-0 z-40 border-t border-gray-200 bg-white">
        <div className="max-w-7xl mx-auto px-2">
          <div className="flex">
            {navItems.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `flex-1 flex flex-col items-center justify-center gap-1 rounded-lg px-2 py-2 h-16 transition-colors ${
                    isActive ? 'text-primary-700' : 'text-gray-600'
                  }`
                }
              >
                <Icon className="w-5 h-5" />
                <span className="text-[11px] font-medium leading-none truncate max-w-full">{label}</span>
              </NavLink>
            ))}
          </div>
        </div>
      </nav>
    </div>
  )
}
