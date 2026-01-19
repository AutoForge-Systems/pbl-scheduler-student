import { useEffect, useState } from 'react'
import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Calendar, Home, Plus, Users, LogOut, User, UserX, Menu, X, ExternalLink } from 'lucide-react'
import logoUrl from '../../logo.png'
import { slotsService } from '../services/scheduler'

const DEFAULT_ALLOWED_SUBJECTS = ['Web Development', 'Compiler Design']
const DEFAULT_PBL_APP_URL = 'https://pbl-form.vercel.app'

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [facultySubject, setFacultySubject] = useState(null)
  const [isSubjectLoading, setIsSubjectLoading] = useState(false)
  const [allowedSubjects, setAllowedSubjects] = useState([])
  const [isSubjectModalOpen, setIsSubjectModalOpen] = useState(false)
  const [selectedSubject, setSelectedSubject] = useState('')
  const [subjectError, setSubjectError] = useState(null)

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

  useEffect(() => {
    let isMounted = true

    async function loadSubject() {
      if (!user) {
        setFacultySubject(null)
        setIsSubjectLoading(false)
        setAllowedSubjects([])
        setIsSubjectModalOpen(false)
        setSelectedSubject('')
        setSubjectError(null)
        return
      }

      setIsSubjectLoading(true)
      try {
        const data = await slotsService.getMySubject()
        if (!isMounted) return
        setFacultySubject(data?.subject || null)
        const allowed = Array.isArray(data?.allowed_subjects) && data.allowed_subjects.length
          ? data.allowed_subjects
          : DEFAULT_ALLOWED_SUBJECTS
        setAllowedSubjects(allowed)
        const shouldPrompt = !data?.subject
        setIsSubjectModalOpen(shouldPrompt)
        setSelectedSubject('')
        setSubjectError(null)
      } catch (err) {
        if (!isMounted) return
        setFacultySubject(null)
        setAllowedSubjects(DEFAULT_ALLOWED_SUBJECTS)
        // If we can't load subject from API, still allow user to set it.
        setIsSubjectModalOpen(true)
        setSelectedSubject('')
        setSubjectError('Could not load your subject. Please select and save again.')
      } finally {
        if (!isMounted) return
        setIsSubjectLoading(false)
      }
    }

    loadSubject()
    return () => {
      isMounted = false
    }
  }, [user])

  async function handleSaveSubject() {
    setSubjectError(null)

    const subject = (selectedSubject || '').trim()
    if (!subject) {
      setSubjectError('Please select a subject')
      return
    }

    try {
      const data = await slotsService.setMySubject(subject)
      setFacultySubject(data?.subject || subject)
      setAllowedSubjects(Array.isArray(data?.allowed_subjects) ? data.allowed_subjects : allowedSubjects)
      setIsSubjectModalOpen(false)
      setSelectedSubject('')
    } catch (err) {
      setSubjectError('Failed to save subject. Please try again.')
    }
  }

  const navItems = [
    { to: '/', icon: Home, label: 'Dashboard' },
    { to: '/slots', icon: Calendar, label: 'My Slots' },
    { to: '/slots/create', icon: Plus, label: 'Create Slot' },
    { to: '/bookings', icon: Users, label: 'Bookings' },
    // { to: '/absent', icon: UserX, label: 'Absent Students' } // Removed per client request
  ]

  const pageTitle = (() => {
    const path = location.pathname
    const match = navItems
      .slice()
      .sort((a, b) => b.to.length - a.to.length)
      .find((i) => (i.to === '/' ? path === '/' : path.startsWith(i.to)))
    return match?.label || 'Faculty Panel'
  })()

  function Sidebar({ onNavigate }) {
    return (
      <div className="p-4 space-y-1">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            onClick={() => onNavigate?.()}
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
    )
  }

  return (
    <div className="h-screen bg-transparent flex flex-col overflow-x-hidden">
      {/* Sticky Top Bar */}
      <header className="bg-gradient-to-b from-[#EAF6F3] to-[#F6FCFA] border-b border-[#D6EDE4] sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-14 sm:h-16">
            <div className="flex items-center gap-2 min-w-0">
              <button
                type="button"
                className="lg:hidden inline-flex items-center justify-center h-11 w-11 rounded-lg hover:bg-gray-100 text-gray-700"
                onClick={() => setMobileNavOpen(true)}
                aria-label="Open navigation"
              >
                <Menu className="w-5 h-5" />
              </button>

              <img
                src={logoUrl}
                alt="PBL Scheduler"
                className="w-8 h-8 object-contain flex-shrink-0"
              />
              <div className="min-w-0">
                <div className="sm:hidden">
                  <div className="text-sm font-semibold text-gray-900 truncate">Graphic Era Hill University</div>
                  <div className="text-xs text-gray-500 truncate">Teacher Panel</div>
                </div>
                <div className="hidden sm:block">
                  <div className="text-xl font-bold text-gray-900">Graphic Era Hill University</div>
                  <div className="text-xs text-gray-500">Teacher Panel</div>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <div className="hidden sm:flex items-center space-x-2 text-gray-700">
                <User className="w-5 h-5" />
                <span className="text-sm font-medium truncate max-w-[14rem]">{user?.name}</span>
                <span className="text-xs bg-primary-100 text-primary-700 px-2 py-1 rounded">
                  Teacher
                </span>
                <button
                  type="button"
                  onClick={() => {
                    if (!facultySubject) setIsSubjectModalOpen(true)
                  }}
                  className={`text-xs px-2 py-1 rounded ${
                    facultySubject
                      ? 'bg-gray-100 text-gray-700'
                      : 'bg-amber-100 text-amber-800 hover:bg-amber-200'
                  }`}
                  title={facultySubject ? 'Subject is fixed' : 'Click to set subject'}
                >
                  {isSubjectLoading
                    ? 'Subject: Loading…'
                    : facultySubject
                      ? `Subject: ${facultySubject}`
                      : 'Subject: Not set (click)'}
                </button>
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
        <nav className="hidden lg:block w-64 bg-[#F6FCFA] border-r border-[#D6EDE4]">
          <div className="h-full overflow-y-auto">
            <Sidebar />
          </div>
        </nav>

        {/* Main Content */}
        <main className="flex-1 min-h-0 overflow-y-auto px-4 py-4 sm:px-6 sm:py-6 lg:p-8">
          <div className="max-w-5xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>

      {/* First-time Subject Setup Modal */}
      {isSubjectModalOpen && (
        <div className="fixed inset-0 z-[60]">
          <div className="absolute inset-0 bg-black/40" />
          <div className="absolute inset-0 flex items-center justify-center p-4">
            <div className="w-full max-w-md bg-white rounded-xl shadow-xl border border-gray-200 overflow-hidden">
              <div className="p-5 border-b border-gray-200">
                <div className="text-lg font-semibold text-gray-900">Select your subject</div>
                <div className="text-sm text-gray-600 mt-1">
                  This will be fixed for your account and used for all slots.
                </div>
              </div>

              <div className="p-5 space-y-3">
                <label className="block text-sm font-medium text-gray-700">Subject</label>
                <select
                  className="input"
                  value={selectedSubject}
                  onChange={(e) => setSelectedSubject(e.target.value)}
                >
                  <option value="">Select subject</option>
                  {(allowedSubjects?.length ? allowedSubjects : DEFAULT_ALLOWED_SUBJECTS).map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                {subjectError && (
                  <div className="text-sm text-red-600">{subjectError}</div>
                )}
              </div>

              <div className="p-5 border-t border-gray-200 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={handleLogout}
                  className="h-11 px-4 rounded-lg border border-gray-200 text-gray-700 hover:bg-gray-50"
                >
                  Logout
                </button>
                <button
                  type="button"
                  onClick={handleSaveSubject}
                  className="h-11 px-4 rounded-lg bg-primary-600 text-white hover:bg-primary-700"
                >
                  Save subject
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Mobile Drawer */}
      {mobileNavOpen && (
        <div className="lg:hidden fixed inset-0 z-50">
          <button
            type="button"
            className="absolute inset-0 bg-black/30"
            aria-label="Close navigation"
            onClick={() => setMobileNavOpen(false)}
          />
          <div className="absolute left-0 top-0 h-full w-72 max-w-[85vw] bg-[#F6FCFA] shadow-xl border-r border-[#D6EDE4] flex flex-col">
            <div className="flex items-center justify-between px-4 h-14 border-b border-gray-200">
              <div className="text-sm font-semibold text-gray-900">Menu</div>
              <button
                type="button"
                className="inline-flex items-center justify-center h-11 w-11 rounded-lg hover:bg-gray-100 text-gray-700"
                onClick={() => setMobileNavOpen(false)}
                aria-label="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              <Sidebar onNavigate={() => setMobileNavOpen(false)} />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
