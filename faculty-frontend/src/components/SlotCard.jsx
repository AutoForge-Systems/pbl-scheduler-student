import { Clock, User, Trash2, CheckCircle, BookOpen } from 'lucide-react'
import { formatTimeRange } from '../utils/dateUtils'

export default function SlotCard({ slot, onDelete, isDeleting }) {
  const hasBooking = slot.has_booking || slot.booking
  const booking = slot.booking

  return (
    <div className={`card p-4 ${slot.is_past ? 'opacity-60' : ''}`}>
      <div className="flex justify-between items-start">
        <div className="space-y-2 flex-1">
          {/* Subject */}
          {slot.subject && (
            <div className="flex items-center space-x-2">
              <BookOpen className="w-4 h-4 text-primary-600" />
              <span className="font-medium text-primary-700">{slot.subject}</span>
            </div>
          )}

          {/* Time */}
          <div className="flex items-center space-x-2 text-gray-900">
            <Clock className="w-4 h-4 text-primary-500" />
            <span className="font-medium">
              {formatTimeRange(slot.start_time, slot.end_time)}
            </span>
            <span className="text-sm text-gray-500">
              ({slot.duration_minutes} min)
            </span>
          </div>

          {/* Booking Status */}
          {hasBooking && booking ? (
            <div className="flex items-center space-x-2">
              <CheckCircle className="w-4 h-4 text-green-500" />
              <span className="text-green-700 font-medium">Booked</span>
              <span className="text-gray-600">by {booking.student.name}</span>
            </div>
          ) : (
            <div className="flex items-center space-x-2 text-gray-500">
              <div className="w-2 h-2 bg-gray-300 rounded-full" />
              <span>Available</span>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center space-x-2">
          {/* Status Badge */}
          {slot.is_past ? (
            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">
              Past
            </span>
          ) : hasBooking ? (
            <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded">
              Confirmed
            </span>
          ) : (
            <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">
              Open
            </span>
          )}

          {/* Delete button - only show if not booked and not past */}
          {!hasBooking && !slot.is_past && (
            <button
              onClick={() => onDelete(slot)}
              disabled={isDeleting}
              className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
              title="Delete slot"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
