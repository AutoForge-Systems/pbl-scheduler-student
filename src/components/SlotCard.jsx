import { Clock, User, BookOpen } from 'lucide-react'
import { formatTimeRange } from '../utils/dateUtils'
import { STUDENT_CANCELLATION_WINDOW_HOURS } from '../constants/rules'

export default function SlotCard({ slot, onBook, isBooking, isBookedForSubject, isBlockedForSubject }) {
  const canBook = !isBookedForSubject && !isBlockedForSubject && !slot.has_booking

  const startsInMs = new Date(slot.start_time).getTime() - Date.now()
  const startsWithinCancellationWindow =
    Number.isFinite(startsInMs) && startsInMs > 0 && startsInMs < STUDENT_CANCELLATION_WINDOW_HOURS * 60 * 60 * 1000

  return (
    <div className="card p-4 hover:shadow-md transition-shadow">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="space-y-2 min-w-0">
          {/* Subject */}
          {slot.subject && (
            <div className="flex items-center space-x-2">
              <BookOpen className="w-4 h-4 text-primary-600" />
              <span className="font-medium text-primary-700 truncate">{slot.subject}</span>
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

          {/* Faculty */}
          <div className="flex items-center space-x-2 text-gray-600">
            <User className="w-4 h-4" />
            <span className="truncate">{slot.faculty.name}</span>
          </div>
        </div>

        {/* Book Button */}
        <div className="w-full sm:w-auto">
          {isBookedForSubject ? (
            <div className="w-full sm:w-auto text-sm text-gray-600 px-3 py-2 bg-gray-100 rounded-lg">
              Already booked for this subject
            </div>
          ) : isBlockedForSubject ? (
            <div className="w-full sm:w-auto text-sm text-orange-800 px-3 py-2 bg-orange-50 border border-orange-200 rounded-lg">
              Blocked due to absence
            </div>
          ) : (
            <div className="flex flex-col gap-2 items-stretch sm:items-end">
              <button
                onClick={() => onBook(slot)}
                disabled={isBooking || !canBook}
                className={`btn-primary text-sm w-full sm:w-auto ${!canBook ? 'opacity-60' : ''}`}
              >
                {isBooking ? 'Booking...' : 'Book Slot'}
              </button>

              <div
                className={`text-[11px] sm:text-xs leading-snug ${
                  startsWithinCancellationWindow
                    ? 'text-orange-700'
                    : 'text-gray-500'
                }`}
              >
                Note: Bookings made within {STUDENT_CANCELLATION_WINDOW_HOURS} hours cannot be cancelled.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
