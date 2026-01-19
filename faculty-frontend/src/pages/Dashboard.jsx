import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Calendar, Users, Plus, Clock, GraduationCap } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { slotsService, bookingsService } from '../services/scheduler'
import { formatDate, formatTimeRange } from '../utils/dateUtils'
import LoadingSpinner from '../components/LoadingSpinner'
import Alert from '../components/Alert'
import PageHeader from '../components/ui/PageHeader'
import NoticeBanner from '../components/ui/NoticeBanner'

export default function Dashboard() {
  const { user } = useAuth()
  const [stats, setStats] = useState({
    totalSlots: 0,
    availableSlots: 0,
    bookedSlots: 0,
    upcomingBookings: []
  })
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadDashboardData()
  }, [])

  async function loadDashboardData() {
    setIsLoading(true)
    setError(null)

    try {
      const [slots, bookings] = await Promise.all([
        slotsService.getMySlots({ future_only: 'true' }),
        bookingsService.getBookings({ confirmed_only: 'true' })
      ])

      const available = slots.filter(s => !s.has_booking && !s.booking)
      const booked = slots.filter(s => s.has_booking || s.booking)

      setStats({
        totalSlots: slots.length,
        availableSlots: available.length,
        bookedSlots: booked.length,
        upcomingBookings: bookings.slice(0, 3)
      })
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
        <div className="flex flex-col sm:flex-row gap-3">
          <Link to="/slots/create" className="btn-primary flex items-center justify-center gap-2 w-full sm:w-auto">
            <Plus className="w-4 h-4" />
            <span>Create New Slot</span>
          </Link>
          <Link to="/slots" className="btn-secondary flex items-center justify-center gap-2 w-full sm:w-auto">
            <Calendar className="w-4 h-4" />
            <span>View All Slots</span>
          </Link>
        </div>
      </div>

      {error && (
        <Alert variant="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <NoticeBanner>
        Past bookings are hidden after the slot time. Future slots remain visible.
      </NoticeBanner>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Total Slots */}
        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Slots</p>
              <p className="text-3xl font-bold text-gray-900 mt-1">
                {stats.totalSlots}
              </p>
            </div>
            <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center">
              <Calendar className="w-6 h-6 text-blue-600" />
            </div>
          </div>
        </div>

        {/* Available Slots */}
        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Available</p>
              <p className="text-3xl font-bold text-primary-600 mt-1">
                {stats.availableSlots}
              </p>
            </div>
            <div className="w-12 h-12 bg-primary-100 rounded-full flex items-center justify-center">
              <Clock className="w-6 h-6 text-primary-600" />
            </div>
          </div>
        </div>

        {/* Booked Slots */}
        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Booked</p>
              <p className="text-3xl font-bold text-purple-600 mt-1">
                {stats.bookedSlots}
              </p>
            </div>
            <div className="w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center">
              <Users className="w-6 h-6 text-purple-600" />
            </div>
          </div>
        </div>
      </div>

      {/* Upcoming Bookings */}
      <div className="card p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center space-x-2">
            <Users className="w-5 h-5 text-primary-600" />
            <span>Upcoming Appointments</span>
          </h2>
          <Link to="/bookings" className="text-primary-600 hover:text-primary-700 text-sm font-medium">
            View All →
          </Link>
        </div>

        {stats.upcomingBookings.length > 0 ? (
          <div className="space-y-3">
            {stats.upcomingBookings.map((booking) => (
              <div
                key={booking.id}
                className="flex justify-between items-center p-3 bg-gray-50 rounded-lg"
              >
                <div>
                  <p className="font-medium text-gray-900">
                    {booking.student.name}
                  </p>
                  <p className="text-sm text-gray-600">
                    {formatDate(booking.slot.start_time, 'EEE, MMM d')} •{' '}
                    {formatTimeRange(booking.slot.start_time, booking.slot.end_time)}
                  </p>
                </div>
                <span className="px-2 py-1 bg-green-100 text-green-700 text-xs rounded-full">
                  Confirmed
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-6 text-gray-500">
            <Users className="w-12 h-12 mx-auto mb-2 text-gray-400" />
            <p>No upcoming appointments</p>
          </div>
        )}
      </div>
    </div>
  )
}
