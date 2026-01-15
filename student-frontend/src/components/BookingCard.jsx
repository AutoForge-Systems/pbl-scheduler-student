import { Calendar, Clock, User, X } from 'lucide-react'
import { formatDate, formatTimeRange, getRelativeTime } from '../utils/dateUtils'

export default function BookingCard({ booking, onCancel, isCancelling }) {
  const isConfirmed = booking.status === 'confirmed'
  const isCancelled = booking.status === 'cancelled'
  const isCompleted = booking.status === 'completed'
  const isAbsent = booking.status === 'absent'

  const statusStyles = isConfirmed
    ? 'bg-green-100 text-green-800'
    : isCompleted
    ? 'bg-blue-100 text-blue-800'
    : isAbsent
    ? 'bg-orange-100 text-orange-800'
    : isCancelled
    ? 'bg-red-100 text-red-800'
    : 'bg-gray-100 text-gray-800'

  return (
    <div className={`card p-4 sm:p-6 ${isCancelled ? 'opacity-60' : ''}`}>
      {/* Status Badge */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-4">
        <span
          className={`px-3 py-1 rounded-full text-sm font-medium inline-flex w-fit ${statusStyles}`}
        >
          {booking.status.charAt(0).toUpperCase() + booking.status.slice(1)}
        </span>

        {isConfirmed && booking.can_cancel && (
          <button
            onClick={() => onCancel(booking)}
            disabled={isCancelling}
            className="btn-danger text-sm inline-flex items-center justify-center gap-2 w-full sm:w-auto"
          >
            <X className="w-4 h-4" />
            <span>{isCancelling ? 'Cancelling...' : 'Cancel'}</span>
          </button>
        )}
      </div>

      {/* Booking Details */}
      <div className="space-y-3">
        {/* Date */}
        <div className="flex items-center space-x-3 text-gray-900">
          <Calendar className="w-5 h-5 text-primary-500" />
          <div>
            <span className="font-medium">
              {formatDate(booking.slot.start_time, 'EEEE, MMMM d, yyyy')}
            </span>
            {isConfirmed && (
              <span className="ml-2 text-sm text-gray-500">
                ({getRelativeTime(booking.slot.start_time)})
              </span>
            )}
          </div>
        </div>

        {/* Time */}
        <div className="flex items-center space-x-3 text-gray-700">
          <Clock className="w-5 h-5 text-gray-400" />
          <span>{formatTimeRange(booking.slot.start_time, booking.slot.end_time)}</span>
          <span className="text-sm text-gray-500">
            ({booking.slot.duration_minutes} min)
          </span>
        </div>

        {/* Faculty */}
        <div className="flex items-center space-x-3 text-gray-700">
          <User className="w-5 h-5 text-gray-400" />
          <span>with {booking.faculty.name}</span>
        </div>
      </div>

      {/* Cancellation Info */}
      {isCancelled && booking.cancellation_reason && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <p className="text-sm text-gray-600">
            <span className="font-medium">Cancellation reason:</span>{' '}
            {booking.cancellation_reason}
          </p>
        </div>
      )}

      {/* Warning if can't cancel */}
      {isConfirmed && !booking.can_cancel && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <p className="text-sm text-yellow-700 bg-yellow-50 px-3 py-2 rounded-lg">
            This booking can no longer be cancelled (within cancellation window).
          </p>
        </div>
      )}
    </div>
  )
}
