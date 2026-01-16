import { useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Calendar, Plus, RefreshCw, Filter, ToggleLeft, ToggleRight, Trash2, Clock, BookOpen, User, CheckCircle, XCircle, UserX } from 'lucide-react'
import { slotsService, bookingsService } from '../services/scheduler'
import { formatDate, formatTimeRange } from '../utils/dateUtils'
import LoadingSpinner from '../components/LoadingSpinner'
import Alert from '../components/Alert'
import { getApiErrorMessage } from '../utils/errorUtils'

export default function MySlots() {
  const location = useLocation()
  const [slots, setSlots] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isDeletingToday, setIsDeletingToday] = useState(false)
  const [isTogglingAvailability, setIsTogglingAvailability] = useState(false)
  const [isUpdatingBooking, setIsUpdatingBooking] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(location.state?.success || null)
  const [dateFilter, setDateFilter] = useState('')
  const [showPast, setShowPast] = useState(false)
  
  // Availability state
  const [isAvailable, setIsAvailable] = useState(true)
  

  useEffect(() => {
    loadSlots()
    loadAvailability()
  }, [dateFilter, showPast])

  // Clear location state after reading
  useEffect(() => {
    if (location.state?.success) {
      window.history.replaceState({}, document.title)
    }
  }, [location.state])

  async function loadSlots() {
    setIsLoading(true)
    setError(null)

    try {
      const params = { future_only: showPast ? 'false' : 'true' }
      if (dateFilter) {
        params.date = dateFilter
      }
      const data = await slotsService.getMySlots(params)
      const sorted = [...data].sort((a, b) => new Date(a.start_time) - new Date(b.start_time))
      setSlots(sorted)
    } catch (err) {
      console.error('Failed to load slots:', err)
      setError('Failed to load your slots')
    } finally {
      setIsLoading(false)
    }
  }

  async function loadAvailability() {
    try {
      const data = await slotsService.getAvailability()
      setIsAvailable(data.is_available)
    } catch (err) {
      console.error('Failed to load availability:', err)
    }
  }

  async function handleToggleAvailability() {
    setIsTogglingAvailability(true)
    setError(null)

    try {
      const newStatus = !isAvailable
      await slotsService.setAvailability(newStatus)
      setIsAvailable(newStatus)
      setSuccess(newStatus 
        ? 'You are now available. Students can see your slots.' 
        : 'You are now busy. Students cannot see your slots.'
      )
    } catch (err) {
      console.error('Failed to toggle availability:', err)
      setError('Failed to update availability status')
    } finally {
      setIsTogglingAvailability(false)
    }
  }

  async function handleDeleteTodaysSlots() {
    const ok = confirm("Delete ALL of today's slots? This cannot be undone.")
    if (!ok) return

    setIsDeletingToday(true)
    setError(null)

    try {
      const result = await slotsService.deleteTodaysSlots()
      setSuccess(result.message || "Deleted today's slots")
      loadSlots()
    } catch (err) {
      console.error("Failed to delete today's slots:", err)
      setError(getApiErrorMessage(err, "Failed to delete today's slots"))
    } finally {
      setIsDeletingToday(false)
    }
  }

  async function handleDelete(slot) {
    if (!confirm('Are you sure you want to delete this slot?')) {
      return
    }

    setIsDeleting(true)
    setError(null)

    try {
      await slotsService.deleteSlot(slot.id)
      setSuccess('Slot deleted successfully')
      loadSlots()
    } catch (err) {
      console.error('Failed to delete slot:', err)
      setError(getApiErrorMessage(err, 'Failed to delete slot'))
    } finally {
      setIsDeleting(false)
    }
  }

  async function handleCancelBooking(bookingId) {
    const reason = prompt('Cancellation reason (optional):', '')
    if (reason === null) return

    setIsUpdatingBooking(true)
    setError(null)

    try {
      await bookingsService.cancelBooking(bookingId, reason)
      setSuccess('Booking cancelled successfully')
      loadSlots()
    } catch (err) {
      console.error('Failed to cancel booking:', err)
      setError(getApiErrorMessage(err, 'Failed to cancel booking'))
    } finally {
      setIsUpdatingBooking(false)
    }
  }

  async function handleMarkEvaluated(bookingId) {
    const ok = confirm('Mark this booking as evaluated (completed)?')
    if (!ok) return

    setIsUpdatingBooking(true)
    setError(null)

    try {
      await bookingsService.completeBooking(bookingId)
      setSuccess('Marked as evaluated')
      loadSlots()
    } catch (err) {
      console.error('Failed to complete booking:', err)
      setError(getApiErrorMessage(err, 'Failed to mark as evaluated'))
    } finally {
      setIsUpdatingBooking(false)
    }
  }

  async function handleMarkAbsent(bookingId) {
    const ok = confirm('Mark this booking as absent?')
    if (!ok) return

    setIsUpdatingBooking(true)
    setError(null)

    try {
      await bookingsService.markAbsent(bookingId)
      setSuccess('Marked as absent')
      loadSlots()
    } catch (err) {
      console.error('Failed to mark absent:', err)
      setError(getApiErrorMessage(err, 'Failed to mark absent'))
    } finally {
      setIsUpdatingBooking(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header with Availability Toggle */}
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">My Availability Slots</h1>
          <p className="text-gray-600 mt-1">
            Manage your appointment availability
          </p>
        </div>

        {/* Availability Toggle - Top Right */}
        <div className="flex items-center space-x-4">
          <button
            onClick={handleToggleAvailability}
            disabled={isTogglingAvailability}
            className={`
              flex items-center space-x-2 px-4 py-2 rounded-lg font-medium transition-all
              ${isAvailable 
                ? 'bg-green-100 text-green-700 hover:bg-green-200' 
                : 'bg-red-100 text-red-700 hover:bg-red-200'
              }
              ${isTogglingAvailability ? 'opacity-50 cursor-not-allowed' : ''}
            `}
          >
            {isAvailable ? (
              <>
                <ToggleRight className="w-5 h-5" />
                <span>Available</span>
              </>
            ) : (
              <>
                <ToggleLeft className="w-5 h-5" />
                <span>Busy</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Action Bar */}
      <div className="flex flex-wrap gap-3">
        <button
          onClick={() => loadSlots()}
          disabled={isLoading}
          className="btn-secondary flex items-center justify-center space-x-2 w-full sm:w-auto"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
        <Link to="/slots/create" className="btn-primary flex items-center justify-center space-x-2 w-full sm:w-auto">
          <Plus className="w-4 h-4" />
          <span>Create Schedule</span>
        </Link>

        <button
          onClick={handleDeleteTodaysSlots}
          disabled={isDeletingToday}
          className="btn-secondary flex items-center justify-center space-x-2 border-red-300 text-red-700 hover:bg-red-50 w-full sm:w-auto"
        >
          <Trash2 className={`w-4 h-4 ${isDeletingToday ? 'animate-spin' : ''}`} />
          <span>{isDeletingToday ? "Deleting..." : "Delete All Today's Slots"}</span>
        </button>
      </div>

      {/* Filters */}
      <div className="card p-4">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center space-x-2">
            <Filter className="w-5 h-5 text-gray-400" />
            <span className="text-sm text-gray-600">Filters:</span>
          </div>
          
          <div className="flex items-center space-x-2">
            <label htmlFor="date-filter" className="text-sm text-gray-600">
              Date:
            </label>
            <input
              id="date-filter"
              type="date"
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value)}
              className="input w-full sm:w-auto"
            />
            {dateFilter && (
              <button
                onClick={() => setDateFilter('')}
                className="text-sm text-primary-600 hover:text-primary-700"
              >
                Clear
              </button>
            )}
          </div>

          <label className="flex items-center space-x-2 cursor-pointer">
            <input
              type="checkbox"
              checked={showPast}
              onChange={(e) => setShowPast(e.target.checked)}
              className="w-4 h-4 text-primary-600 rounded"
            />
            <span className="text-sm text-gray-600">Show past slots</span>
          </label>
        </div>
      </div>

      {/* Availability Status Banner */}
      {!isAvailable && (
        <Alert variant="warning">
          <strong>You are currently marked as Busy.</strong> Students cannot see your available slots. 
          Toggle your status to "Available" when you're ready.
        </Alert>
      )}

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

      {/* Slots List */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner size="lg" />
        </div>
      ) : slots.length === 0 ? (
        <div className="card p-12 text-center">
          <Calendar className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            No Slots Found
          </h3>
          <p className="text-gray-600 mb-4">
            {dateFilter
              ? `No slots for ${formatDate(dateFilter, 'MMMM d, yyyy')}`
              : "You haven't created any slots yet"}
          </p>
          <Link to="/slots/create" className="btn-primary inline-flex items-center space-x-2">
            <Plus className="w-4 h-4" />
            <span>Create Your First Schedule</span>
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-gray-500">
            {slots.length} slot{slots.length !== 1 ? 's' : ''} found
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {slots.map((slot) => {
              const booking = slot.booking
              const bookingStatus = booking?.status
              const isConfirmed = bookingStatus === 'confirmed'
              const isCompleted = bookingStatus === 'completed'
              const isCancelled = bookingStatus === 'cancelled'
              const isAbsent = bookingStatus === 'absent'

              const dateLabel = slot?.start_time ? formatDate(slot.start_time, 'EEE, MMM d') : ''
              const timeLabel = slot?.start_time && slot?.end_time ? formatTimeRange(slot.start_time, slot.end_time) : ''

              const statusLabel = slot.is_past
                ? 'past'
                : isConfirmed
                ? 'confirmed'
                : isCompleted
                ? 'completed'
                : isAbsent
                ? 'absent'
                : isCancelled
                ? 'open'
                : slot.is_available
                ? 'open'
                : 'closed'

              const canDeleteSlot = !slot.is_past && (!isConfirmed)
              const canCancel = isConfirmed
              const canEvaluate = isConfirmed
              const canMarkAbsent = isConfirmed

              return (
                <div key={slot.id} className="card p-4 hover:shadow-md transition-shadow">
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-2 min-w-0">
                      {slot.subject && (
                        <div className="flex items-center space-x-2">
                          <BookOpen className="w-4 h-4 text-primary-600" />
                          <span className="font-semibold text-primary-700 truncate">{slot.subject}</span>
                        </div>
                      )}

                      <div className="flex items-center space-x-2 text-gray-900">
                        <Calendar className="w-4 h-4 text-gray-500" />
                        <span className="font-medium truncate">{dateLabel}</span>
                      </div>

                      <div className="flex items-center space-x-2 text-gray-700">
                        <Clock className="w-4 h-4 text-gray-500" />
                        <span className="truncate">{timeLabel}</span>
                      </div>

                      {(isConfirmed || isCompleted) && booking?.student && (
                        <div className="flex items-center space-x-2 text-gray-700">
                          <User className="w-4 h-4 text-gray-500" />
                          <span className="truncate">
                            {booking.student.name || booking.student.email || 'Student'}
                          </span>
                        </div>
                      )}

                      <div className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
                        {statusLabel}
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-2">
                    <button
                      type="button"
                      onClick={() => handleMarkEvaluated(booking.id)}
                      disabled={!canEvaluate || isUpdatingBooking}
                      className={`btn-secondary w-full flex items-center justify-center space-x-2 ${
                        canEvaluate ? 'text-green-700 border-green-300 hover:bg-green-50' : 'opacity-50 cursor-not-allowed'
                      }`}
                      title={canEvaluate ? 'Mark as evaluated' : 'Only confirmed bookings can be evaluated'}
                    >
                      <CheckCircle className="w-4 h-4" />
                      <span>{isUpdatingBooking && canEvaluate ? 'Saving...' : 'Evaluated'}</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => handleMarkAbsent(booking.id)}
                      disabled={!canMarkAbsent || isUpdatingBooking}
                      className={`btn-secondary w-full flex items-center justify-center space-x-2 ${
                        canMarkAbsent ? 'text-orange-700 border-orange-300 hover:bg-orange-50' : 'opacity-50 cursor-not-allowed'
                      }`}
                      title={canMarkAbsent ? 'Mark as absent' : 'Only confirmed bookings can be marked absent'}
                    >
                      <UserX className="w-4 h-4" />
                      <span>{isUpdatingBooking && canMarkAbsent ? 'Saving...' : 'Absent'}</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        if (canCancel) return handleCancelBooking(booking.id)
                        if (canDeleteSlot) return handleDelete(slot)
                      }}
                      disabled={isDeleting || isUpdatingBooking || (!canCancel && !canDeleteSlot)}
                      className={`btn-secondary w-full flex items-center justify-center space-x-2 ${
                        canCancel
                          ? 'text-red-700 border-red-300 hover:bg-red-50'
                          : canDeleteSlot
                          ? 'text-red-700 border-red-300 hover:bg-red-50'
                          : 'opacity-50 cursor-not-allowed'
                      }`}
                      title={canCancel ? 'Cancel booking' : canDeleteSlot ? 'Delete slot' : 'Action not available'}
                    >
                      <XCircle className="w-4 h-4" />
                      <span>{canCancel ? 'Cancel' : 'Delete'}</span>
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
