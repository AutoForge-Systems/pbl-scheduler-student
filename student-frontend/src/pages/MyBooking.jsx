import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { BookOpen, Calendar, History } from 'lucide-react'
import { bookingsService } from '../services/scheduler'
import LoadingSpinner from '../components/LoadingSpinner'
import Alert from '../components/Alert'
import BookingCard from '../components/BookingCard'
import { getApiErrorMessage } from '../utils/errorUtils'

export default function MyBooking() {
  const [activeBookings, setActiveBookings] = useState([])
  const [pastBookings, setPastBookings] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [isCancelling, setIsCancelling] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  const [showCancelModal, setShowCancelModal] = useState(false)
  const [bookingToCancel, setBookingToCancel] = useState(null)
  const [cancelReason, setCancelReason] = useState('')
  const [blockedSubjects, setBlockedSubjects] = useState([])

  useEffect(() => {
    loadBookings()
  }, [])

  // Keep UI fresh if faculty changes status (no realtime; poll + focus refresh)
  useEffect(() => {
    function onFocus() {
      loadBookings()
    }

    window.addEventListener('focus', onFocus)
    const intervalId = setInterval(() => {
      loadBookings()
    }, 15000)

    return () => {
      window.removeEventListener('focus', onFocus)
      clearInterval(intervalId)
    }
  }, [])

  async function loadBookings() {
    setIsLoading(true)
    setError(null)

    try {
      const [allBookings, blocked] = await Promise.all([
        bookingsService.getMyBookings(),
        bookingsService.getBlockedSubjects()
      ])
      
      const current = allBookings.filter(b => b.status === 'confirmed')
      const past = allBookings.filter(b => b.status !== 'confirmed')

      const blockedList = blocked?.blocked_subjects || []
      setBlockedSubjects(Array.isArray(blockedList) ? blockedList : [])
      
      setActiveBookings(current)
      setPastBookings(past)

      // If user had cancel modal open and booking is no longer confirmed, close it.
      if (bookingToCancel) {
        const stillConfirmed = allBookings.some(b => b.id === bookingToCancel.id && b.status === 'confirmed')
        if (!stillConfirmed) {
          setShowCancelModal(false)
          setBookingToCancel(null)
          setCancelReason('')
          setSuccess(null)
          setError('This booking can no longer be cancelled. Please contact your faculty.')
        }
      }
    } catch (err) {
      console.error('Failed to load bookings:', err)
      setError('Failed to load your bookings')
    } finally {
      setIsLoading(false)
    }
  }

  async function handleCancel() {
    if (!bookingToCancel) return

    setIsCancelling(true)
    setError(null)

    try {
      await bookingsService.cancelBooking(bookingToCancel.id, cancelReason)
      setSuccess('Booking cancelled successfully')
      setShowCancelModal(false)
      setBookingToCancel(null)
      setCancelReason('')
      loadBookings()
    } catch (err) {
      console.error('Failed to cancel booking:', err)
      setError(getApiErrorMessage(err, 'Failed to cancel booking'))
    } finally {
      setIsCancelling(false)
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
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">My Booking</h1>
        <p className="text-gray-600 mt-1">
          View and manage your appointment
        </p>
      </div>

      {/* Alerts */}
      {error && (
        <Alert variant="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert variant="success" onClose={() => setSuccess(null)}>
          {success}
        </Alert>
      )}

      {blockedSubjects.length > 0 && (
        <Alert variant="warning" onClose={() => setBlockedSubjects([])}>
          {blockedSubjects.length === 1
            ? blockedSubjects[0]?.detail || `You were marked absent for ${blockedSubjects[0]?.subject}. Please contact your faculty to book another slot.`
            : `You were marked absent for: ${blockedSubjects.map(b => b.subject).filter(Boolean).join(', ')}. Please contact your faculty to book another slot.`}
        </Alert>
      )}

      {/* Current Booking */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center space-x-2">
          <BookOpen className="w-5 h-5 text-primary-600" />
          <span>Active Appointment</span>
        </h2>

        {activeBookings.length > 0 ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {activeBookings.map((booking) => (
              <BookingCard
                key={booking.id}
                booking={booking}
                onCancel={() => {
                  setBookingToCancel(booking)
                  setShowCancelModal(true)
                }}
                isCancelling={isCancelling && bookingToCancel?.id === booking.id}
              />
            ))}
          </div>
        ) : (
          <div className="card p-8 text-center">
            <Calendar className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              No Active Booking
            </h3>
            <p className="text-gray-600 mb-4">
              You don't have any upcoming appointments
            </p>
            <Link to="/slots" className="btn-primary inline-block">
              Book an Appointment
            </Link>
          </div>
        )}
      </div>

      {/* Past Bookings */}
      {pastBookings.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center space-x-2">
            <History className="w-5 h-5 text-gray-500" />
            <span>Past Bookings</span>
          </h2>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {pastBookings.map((booking) => (
              <BookingCard
                key={booking.id}
                booking={booking}
                onCancel={() => {}}
                isCancelling={false}
              />
            ))}
          </div>
        </div>
      )}

      {/* Cancel Modal */}
      {showCancelModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-5 sm:p-6 w-full max-w-md mx-4 max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Cancel Appointment
            </h3>
            <p className="text-gray-600 mb-4">
              Are you sure you want to cancel this appointment?
            </p>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Reason (optional)
              </label>
              <textarea
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                className="input h-24 min-h-[96px]"
                placeholder="Enter a reason for cancellation..."
              />
            </div>

            <div className="flex flex-col sm:flex-row gap-3">
              <button
                onClick={() => {
                  setShowCancelModal(false)
                  setBookingToCancel(null)
                }}
                disabled={isCancelling}
                className="btn-secondary w-full sm:flex-1"
              >
                Keep Appointment
              </button>
              <button
                onClick={handleCancel}
                disabled={isCancelling}
                className="btn-danger w-full sm:flex-1"
              >
                {isCancelling ? 'Cancelling...' : 'Cancel Appointment'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
