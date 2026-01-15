import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Calendar, Clock, ArrowRight, BookOpen } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { bookingsService, slotsService } from '../services/scheduler'
import { formatDate, formatTimeRange, getRelativeTime } from '../utils/dateUtils'
import LoadingSpinner from '../components/LoadingSpinner'
import Alert from '../components/Alert'

export default function Dashboard() {
  const { user } = useAuth()
  const [currentBookings, setCurrentBookings] = useState([])
  const [availableSlotsCount, setAvailableSlotsCount] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

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
    <div className="space-y-8">
      {/* Welcome Section */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">
          Welcome back, {user?.name?.split(' ')[0]}!
        </h1>
        <p className="mt-2 text-gray-600">
          Manage your appointments with faculty members
        </p>
      </div>

      {error && (
        <Alert variant="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Current Booking Card */}
      <div className="card p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center space-x-2">
          <BookOpen className="w-5 h-5 text-primary-600" />
          <span>Your Appointment</span>
        </h2>

        {currentBookings.length > 0 ? (
          <div className="bg-primary-50 rounded-lg p-4">
            <div className="flex justify-between items-start">
              <div className="space-y-2">
                {(() => {
                  const next = [...currentBookings]
                    .filter(b => b?.status === 'confirmed')
                    .sort((a, b) => new Date(a.slot.start_time) - new Date(b.slot.start_time))[0]
                  if (!next) return null
                  return (
                    <>
                <div className="flex items-center space-x-2">
                  <Calendar className="w-4 h-4 text-primary-600" />
                  <span className="font-medium text-gray-900">
                    {formatDate(next.slot.start_time, 'EEEE, MMMM d')}
                  </span>
                  <span className="text-sm text-gray-500">
                    ({getRelativeTime(next.slot.start_time)})
                  </span>
                </div>
                <div className="flex items-center space-x-2 text-gray-700">
                  <Clock className="w-4 h-4" />
                  <span>
                    {formatTimeRange(
                      next.slot.start_time,
                      next.slot.end_time
                    )}
                  </span>
                </div>
                <p className="text-gray-600">
                  with <strong>{next.faculty.name}</strong>
                </p>
                <p className="text-sm text-gray-500">
                  Active bookings: {currentBookings.filter(b => b?.status === 'confirmed').length}
                </p>
                    </>
                  )
                })()}
              </div>

              <Link
                to="/booking"
                className="btn-primary text-sm flex items-center space-x-1"
              >
                <span>View Details</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        ) : (
          <div className="text-center py-6">
            <p className="text-gray-500 mb-4">
              You don't have any upcoming appointments
            </p>
            <Link to="/slots" className="btn-primary inline-flex items-center space-x-2">
              <Calendar className="w-4 h-4" />
              <span>Book an Appointment</span>
            </Link>
          </div>
        )}
      </div>

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
    </div>
  )
}
