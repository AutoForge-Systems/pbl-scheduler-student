import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Calendar, Clock, ArrowRight, BookOpen, GraduationCap } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { bookingsService, slotsService } from '../services/scheduler'
import { formatDate, formatTimeRange, getRelativeTime } from '../utils/dateUtils'
import LoadingSpinner from '../components/LoadingSpinner'
import Alert from '../components/Alert'
import PageHeader from '../components/ui/PageHeader'
import NoticeBanner from '../components/ui/NoticeBanner'
import StatusPanel from '../components/ui/StatusPanel'

export default function Dashboard() {
  const { user } = useAuth()
  const [currentBookings, setCurrentBookings] = useState([])
  const [availableSlotsCount, setAvailableSlotsCount] = useState(0)
  const [subjectAvailability, setSubjectAvailability] = useState({
    webDevelopment: false,
    compilerDesign: false
  })
  const [academicYear, setAcademicYear] = useState('3rd Year')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  const SECOND_YEAR_SUBJECTS = new Set(['DAA', 'JAVA', 'Deep Learning'])

  function normalizeSubject(value) {
    return String(value || '').trim().toLowerCase()
  }

  useEffect(() => {
    loadDashboardData()
  }, [])

  async function loadDashboardData() {
    setIsLoading(true)
    setError(null)

    try {
      const [bookings, slots] = await Promise.all([
        bookingsService.getCurrentBooking(),
        slotsService.getAvailable()
      ])

      setCurrentBookings(Array.isArray(bookings) ? bookings : [])
      setAvailableSlotsCount(slots.length)

      const slotSubjects = new Set(
        (Array.isArray(slots) ? slots : [])
          .map((s) => s?.subject)
          .map(normalizeSubject)
          .filter(Boolean)
      )

      setSubjectAvailability({
        webDevelopment: slotSubjects.has('web development'),
        compilerDesign: slotSubjects.has('compiler design')
      })

      const subjects = new Set(
        [
          ...(Array.isArray(bookings) ? bookings : [])
            .map((b) => b?.slot?.subject)
            .filter(Boolean),
          ...(Array.isArray(slots) ? slots : [])
            .map((s) => s?.subject)
            .filter(Boolean)
        ]
          .map(normalizeSubject)
          .filter(Boolean)
      )

      const isSecondYear = Array.from(SECOND_YEAR_SUBJECTS)
        .map(normalizeSubject)
        .some((s) => subjects.has(s))

      setAcademicYear(isSecondYear ? '2nd Year' : '3rd Year')
    } catch (err) {
      console.error('Failed to load dashboard:', err)
      setError('Failed to load dashboard data')
    } finally {
      setIsLoading(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Project Submission"
        subtitle="PBL Form Portal"
        icon={GraduationCap}
      />

      <div className="card p-5 sm:p-6">
        <div className="grid grid-cols-1 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Academic Year</label>
            <div className="input bg-gray-50 text-gray-700 flex items-center">{academicYear}</div>
          </div>
        </div>
      </div>

      {error && (
        <Alert variant="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <NoticeBanner>
        You can book slots daily. Past bookings are hidden after the slot time.
      </NoticeBanner>

      {/* Current Booking Panel */}
      {currentBookings.length > 0 ? (
        <StatusPanel title="Submission Successful" subtitle="Your Booking">
          {(() => {
            const next = [...currentBookings]
              .filter(b => b?.status === 'confirmed')
              .sort((a, b) => new Date(a.slot.start_time) - new Date(b.slot.start_time))[0]
            if (!next) return null
            return (
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-emerald-700" />
                    <div className="font-semibold text-gray-900">
                      {formatDate(next.slot.start_time, 'EEEE, MMMM d')}
                      <span className="ml-2 text-sm font-normal text-gray-500">
                        ({getRelativeTime(next.slot.start_time)})
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-gray-700">
                    <Clock className="w-4 h-4" />
                    <span>{formatTimeRange(next.slot.start_time, next.slot.end_time)}</span>
                  </div>
                  <div className="text-gray-700">
                    Mentor: <span className="font-semibold">{next.faculty.name}</span>
                  </div>
                  <div className="text-sm text-gray-500">
                    Active bookings: {currentBookings.filter(b => b?.status === 'confirmed').length}
                  </div>
                </div>

                <Link to="/booking" className="btn-primary text-sm inline-flex items-center justify-center gap-2">
                  <span>View Details</span>
                  <ArrowRight className="w-4 h-4" />
                </Link>
              </div>
            )
          })()}
        </StatusPanel>
      ) : (
        <div className="card p-6 text-center">
          <div className="text-gray-700 font-semibold">No active booking</div>
          <div className="text-gray-500 mt-1">Book an appointment for today.</div>
          <div className="mt-4">
            <Link to="/slots" className="btn-primary inline-flex items-center gap-2">
              <Calendar className="w-4 h-4" />
              <span>Book an Appointment</span>
            </Link>
          </div>
        </div>
      )}

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Available Slots */}
        <Link
          to="/slots"
          className="card p-6 hover:shadow-md transition-shadow group"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Available Slots</p>
              <p className="text-3xl font-bold text-gray-900 mt-1">
                {availableSlotsCount}
              </p>
            </div>
            <div className="w-12 h-12 bg-primary-100 rounded-full flex items-center justify-center group-hover:bg-primary-200 transition-colors">
              <Calendar className="w-6 h-6 text-primary-600" />
            </div>
          </div>
          <p className="text-sm text-gray-500 mt-4">
            Click to view available time slots
          </p>
        </Link>

        {/* Booking Status */}
        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Booking Status</p>
              <p className="text-xl font-semibold text-gray-900 mt-1">
                {currentBookings.filter(b => b?.status === 'confirmed').length > 0 ? (
                  <span className="text-green-600">
                    {currentBookings.filter(b => b?.status === 'confirmed').length} Active
                  </span>
                ) : (
                  <span className="text-gray-600">No Active Booking</span>
                )}
              </p>
            </div>
            <div
              className={`w-12 h-12 rounded-full flex items-center justify-center ${
                currentBookings.filter(b => b?.status === 'confirmed').length > 0 ? 'bg-green-100' : 'bg-gray-100'
              }`}
            >
              <BookOpen
                className={`w-6 h-6 ${
                  currentBookings.filter(b => b?.status === 'confirmed').length > 0 ? 'text-green-600' : 'text-gray-400'
                }`}
              />
            </div>
          </div>
          <p className="text-sm text-gray-500 mt-4">
            {currentBookings.filter(b => b?.status === 'confirmed').length > 0
              ? 'You can cancel a booking to rebook for that subject'
              : 'Book a slot from available appointments'}
          </p>
        </div>
      </div>

      <div className="card p-6">
        <p className="text-sm text-gray-500">Subject Slots</p>
        <div className="mt-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-gray-700 font-medium">Web Development</div>
            <div className={subjectAvailability.webDevelopment ? 'text-green-600 font-semibold' : 'text-gray-500'}>
              {subjectAvailability.webDevelopment ? 'Available' : 'Not available'}
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div className="text-gray-700 font-medium">Compiler Design</div>
            <div className={subjectAvailability.compilerDesign ? 'text-green-600 font-semibold' : 'text-gray-500'}>
              {subjectAvailability.compilerDesign ? 'Available' : 'Not available'}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
