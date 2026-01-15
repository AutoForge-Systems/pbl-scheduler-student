import { Calendar, Clock, User } from 'lucide-react'
import { formatDate, formatTimeRange, getRelativeTime } from '../utils/dateUtils'

export default function BookingCard({ booking }) {
  const isConfirmed = booking.status === 'confirmed'
  const isCancelled = booking.status === 'cancelled'

  return (
    <div className={`card p-4 ${isCancelled ? 'opacity-60' : ''}`}>
      <div className="flex justify-between items-start">
        <div className="space-y-2">
          {/* Student Info */}
          <div className="flex items-center space-x-2 text-gray-900">
            <User className="w-4 h-4 text-primary-500" />
            <span className="font-medium">{booking.student.name}</span>
            <span className="text-sm text-gray-500">
              ({booking.student.email})
            </span>
          </div>

          {/* Date */}
          <div className="flex items-center space-x-2 text-gray-700">
            <Calendar className="w-4 h-4" />
            <span>
              {formatDate(booking.slot.start_time, 'EEEE, MMMM d, yyyy')}
            </span>
            {isConfirmed && (
              <span className="text-sm text-gray-500">
                ({getRelativeTime(booking.slot.start_time)})
              </span>
            )}
          </div>

          {/* Time */}
          <div className="flex items-center space-x-2 text-gray-600">
            <Clock className="w-4 h-4" />
            <span>{formatTimeRange(booking.slot.start_time, booking.slot.end_time)}</span>
          </div>
        </div>

        {/* Status Badge */}
        <span
          className={`px-3 py-1 rounded-full text-sm font-medium ${
            isConfirmed
              ? 'bg-green-100 text-green-800'
              : isCancelled
              ? 'bg-red-100 text-red-800'
              : 'bg-gray-100 text-gray-800'
          }`}
        >
          {booking.status.charAt(0).toUpperCase() + booking.status.slice(1)}
        </span>
      </div>

      {/* Cancellation Info */}
      {isCancelled && booking.cancellation_reason && (
        <div className="mt-3 pt-3 border-t border-gray-200">
          <p className="text-sm text-gray-600">
            <span className="font-medium">Reason:</span>{' '}
            {booking.cancellation_reason}
          </p>
        </div>
      )}
    </div>
  )
}
