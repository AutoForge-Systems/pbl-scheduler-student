import { useState, useEffect } from 'react'
import { Users, RefreshCw, Filter, Calendar, Clock, BookOpen, User, MoreVertical, X, /*CheckCircle, UserX,*/ ChevronDown, ChevronUp } from 'lucide-react'
import { bookingsService } from '../services/scheduler'
import { formatDate, formatTimeRange } from '../utils/dateUtils'
import LoadingSpinner from '../components/LoadingSpinner'
import Alert from '../components/Alert'
import { getApiErrorMessage } from '../utils/errorUtils'

export default function Bookings() {
  const [bookings, setBookings] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statusFilter, setStatusFilter] = useState('confirmed')
  const [openPopoverId, setOpenPopoverId] = useState(null)
  const [updating, setUpdating] = useState({ id: null, action: null })

  useEffect(() => {
    loadBookings()
  }, [statusFilter])

  // Close popover on outside click / Escape
  useEffect(() => {
    function onMouseDown(e) {
      if (!openPopoverId) return
      const root = e.target.closest?.(`[data-popover-root="${openPopoverId}"]`)
      if (!root) setOpenPopoverId(null)
    }

    function onKeyDown(e) {
      if (e.key === 'Escape') setOpenPopoverId(null)
    }

    document.addEventListener('mousedown', onMouseDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onMouseDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [openPopoverId])

  async function loadBookings() {
    setIsLoading(true)
    setError(null)

    try {
      const params = statusFilter ? { status: statusFilter } : {}
      const data = await bookingsService.getBookings(params)
      setBookings(data)
    } catch (err) {
      console.error('Failed to load bookings:', err)
      setError('Failed to load bookings')
    } finally {
      setIsLoading(false)
    }
  }

  // Removed per client request:
  // async function handleMarkCompleted(bookingId) { ... }
  // async function handleMarkAbsent(bookingId) { ... }

  async function handleCancel(bookingId) {
    const reason = window.prompt('Optional cancellation reason:', '')
    setUpdating({ id: bookingId, action: 'cancel' })
    setError(null)
    try {
      await bookingsService.cancelBooking(bookingId, reason || '')
      await loadBookings()
    } catch (err) {
      console.error('Failed to cancel booking:', err)
      setError(getApiErrorMessage(err, 'Failed to cancel booking'))
    } finally {
      setUpdating({ id: null, action: null })
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Bookings</h1>
          <p className="text-gray-600 mt-1">
            View bookings made by students
          </p>
        </div>

        <button
          onClick={() => loadBookings()}
          disabled={isLoading}
          className="btn-secondary inline-flex items-center justify-center gap-2 w-full sm:w-auto"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filters */}
      <div className="card p-4">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4">
          <Filter className="w-5 h-5 text-gray-400" />
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 w-full">
            <label htmlFor="status-filter" className="text-sm text-gray-600">
              Status:
            </label>
            <select
              id="status-filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="input w-full sm:w-auto"
            >
              <option value="">All</option>
              <option value="confirmed">Confirmed</option>
              <option value="cancelled">Cancelled</option>
              {/* <option value="absent">Absent</option>
              <option value="completed">Completed</option> */}
            </select>
          </div>
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <Alert variant="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Bookings List */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner size="lg" />
        </div>
      ) : bookings.length === 0 ? (
        <div className="card p-12 text-center">
          <Users className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            No Bookings Found
          </h3>
          <p className="text-gray-600">
            {statusFilter
              ? `No ${statusFilter} bookings found`
              : 'No students have booked your slots yet'}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-gray-500">
            {bookings.length} booking{bookings.length !== 1 ? 's' : ''} found
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {bookings.map((booking) => {
              const isOpen = openPopoverId === booking.id
              const slot = booking.slot
              const student = booking.student
              const subject = slot?.subject
              const dateLabel = slot?.start_time ? formatDate(slot.start_time, 'EEE, MMM d') : ''
              const timeLabel = slot?.start_time && slot?.end_time ? formatTimeRange(slot.start_time, slot.end_time) : ''

              const isConfirmed = booking.status === 'confirmed'
              const isBusy = updating.id === booking.id
              const canUpdate = isConfirmed && !isBusy

              return (
                <div
                  key={booking.id}
                  data-popover-root={booking.id}
                  className="card p-4 hover:shadow-md transition-shadow"
                  onClick={(e) => {
                    const isMobile = typeof window !== 'undefined' && window.matchMedia?.('(max-width: 767px)').matches
                    if (!isMobile) return
                    if (e.target.closest?.('button,a,input,select,textarea,label')) return
                    setOpenPopoverId(isOpen ? null : booking.id)
                  }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-2 min-w-0">
                      {subject && (
                        <div className="flex items-center space-x-2">
                          <BookOpen className="w-4 h-4 text-primary-600" />
                          <span className="font-semibold text-primary-700 truncate">{subject}</span>
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

                      <div className="flex items-center space-x-2 text-gray-700">
                        <User className="w-4 h-4 text-gray-500" />
                        <span className="truncate">
                          {student?.name || student?.email || 'Student'}
                        </span>
                      </div>

                      <div className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
                        {booking.status}
                      </div>
                    </div>

                    {/* Mobile: inline expand/collapse */}
                    <div className="md:hidden">
                      <button
                        type="button"
                        onClick={() => setOpenPopoverId(isOpen ? null : booking.id)}
                        className="inline-flex items-center justify-center gap-1 rounded-lg px-3 h-11 text-gray-700 hover:bg-gray-100"
                        aria-expanded={isOpen}
                      >
                        <span className="text-sm font-medium">Details</span>
                        {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </button>
                    </div>

                    {/* Desktop/tablet: popover */}
                    <div className="hidden md:block relative" data-popover-root={booking.id}>
                      <button
                        type="button"
                        onClick={() => setOpenPopoverId(isOpen ? null : booking.id)}
                        className="h-11 w-11 inline-flex items-center justify-center rounded-lg hover:bg-gray-100 text-gray-600"
                        aria-label="Open details"
                        aria-haspopup="menu"
                        aria-expanded={isOpen}
                      >
                        <MoreVertical className="w-5 h-5" />
                      </button>

                      {isOpen && (
                        <div
                          role="menu"
                          className="absolute right-0 top-12 z-20 w-80 rounded-xl border border-gray-200 bg-white shadow-lg"
                        >
                          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
                            <span className="text-sm font-semibold text-gray-900">Booking Details</span>
                            <button
                              type="button"
                              onClick={() => setOpenPopoverId(null)}
                              className="h-11 w-11 inline-flex items-center justify-center rounded-lg hover:bg-gray-100 text-gray-600"
                              aria-label="Close"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </div>

                          <div className="px-4 py-3 space-y-2 text-sm text-gray-700">
                            {student?.email && (
                              <div>
                                <span className="font-medium">Student Email:</span> {student.email}
                              </div>
                            )}
                            {booking.created_at && (
                              <div>
                                <span className="font-medium">Booked At:</span> {formatDate(booking.created_at, 'MMM d, yyyy h:mm a')}
                              </div>
                            )}
                            {booking.cancelled_at && (
                              <div>
                                <span className="font-medium">Cancelled At:</span> {formatDate(booking.cancelled_at, 'MMM d, yyyy h:mm a')}
                              </div>
                            )}
                            {booking.cancellation_reason && (
                              <div>
                                <span className="font-medium">Reason:</span> {booking.cancellation_reason}
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Mobile inline details (no popover/modal) */}
                  {isOpen && (
                    <div className="md:hidden mt-3 pt-3 border-t border-gray-200 text-sm text-gray-700 space-y-2">
                      {student?.email && (
                        <div>
                          <span className="font-medium">Student Email:</span> {student.email}
                        </div>
                      )}
                      {booking.created_at && (
                        <div>
                          <span className="font-medium">Booked At:</span> {formatDate(booking.created_at, 'MMM d, yyyy h:mm a')}
                        </div>
                      )}
                      {booking.cancelled_at && (
                        <div>
                          <span className="font-medium">Cancelled At:</span> {formatDate(booking.cancelled_at, 'MMM d, yyyy h:mm a')}
                        </div>
                      )}
                      {booking.cancellation_reason && (
                        <div>
                          <span className="font-medium">Reason:</span> {booking.cancellation_reason}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Actions */}
                  {isConfirmed && (
                    <div className="mt-4 grid grid-cols-1 md:grid-cols-1 gap-2">
                      {/* Removed Completed and Absent buttons per client request */}
                      {/* <button ...>Completed</button> */}
                      {/* <button ...>Absent</button> */}
                      <button
                        type="button"
                        onClick={() => handleCancel(booking.id)}
                        disabled={!canUpdate}
                        className={`btn-danger w-full flex items-center justify-center space-x-2 ${
                          !canUpdate ? 'opacity-50 cursor-not-allowed' : ''
                        }`}
                      >
                        <X className="w-4 h-4" />
                        <span>
                          {isBusy && updating.action === 'cancel' ? 'Cancelling...' : 'Cancel'}
                        </span>
                      </button>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
