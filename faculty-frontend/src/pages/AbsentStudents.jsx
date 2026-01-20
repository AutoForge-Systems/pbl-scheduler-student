import { useEffect, useState } from 'react'
import { RefreshCw, UserX, BookOpen } from 'lucide-react'
import Alert from '../components/Alert'
import LoadingSpinner from '../components/LoadingSpinner'
import { bookingsService } from '../services/scheduler'
import { formatDate, formatDateTime, formatTimeRange } from '../utils/dateUtils'
import { getApiErrorMessage } from '../utils/errorUtils'

export default function AbsentStudents() {
  const [items, setItems] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [actingKey, setActingKey] = useState(null)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)

  useEffect(() => {
    load()
  }, [])

  async function load() {
    setIsLoading(true)
    setError(null)

    try {
      const data = await bookingsService.getAbsentStudents()
      setItems(Array.isArray(data) ? data : [])
    } catch (err) {
      console.error('Failed to load absent students:', err)
      setError(getApiErrorMessage(err, 'Failed to load absent students'))
    } finally {
      setIsLoading(false)
    }
  }

  async function handleAllowRebooking(row) {
    const key = `${row.student.id}-${row.subject}`
    setActingKey(key)
    setError(null)
    setSuccess(null)

    try {
      await bookingsService.allowRebooking({ bookingId: row.booking_id })
      setSuccess(`Rebooking allowed for ${(row.student.pbl_user_id || row.student.email)} (${row.subject})`)
      await load()
    } catch (err) {
      console.error('Failed to allow rebooking:', err)
      setError(getApiErrorMessage(err, 'Failed to allow rebooking'))
    } finally {
      setActingKey(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Absent Students</h1>
          <p className="text-gray-600 mt-1">Students marked absent for your subject</p>
        </div>

        <button
          onClick={load}
          disabled={isLoading}
          className="btn-secondary inline-flex items-center justify-center gap-2 w-full sm:w-auto"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

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

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner size="lg" />
        </div>
      ) : items.length === 0 ? (
        <div className="card p-12 text-center">
          <UserX className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No Absent Students</h3>
          <p className="text-gray-600">No students have been marked absent yet.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {items.map((row) => (
            <div key={`${row.student.id}-${row.subject}`} className="card p-4">
              <div className="space-y-2">
                <div className="flex items-center space-x-2 text-gray-900">
                  <UserX className="w-4 h-4 text-orange-500" />
                  <span className="font-semibold">{row.student.name}</span>
                </div>

                <div className="text-sm text-gray-600 truncate">
                  Student ID: {row.student.pbl_user_id || row.student.email}
                </div>

                <div className="flex items-center space-x-2">
                  <BookOpen className="w-4 h-4 text-primary-600" />
                  <span className="text-primary-700 font-medium">{row.subject}</span>
                </div>

                <div className="text-sm text-gray-700">
                  <div>
                    <span className="font-medium">Slot:</span>{' '}
                    {row?.slot?.start_time ? formatDate(row.slot.start_time, 'EEE, MMM d') : '—'}
                    {row?.slot?.start_time && row?.slot?.end_time
                      ? ` • ${formatTimeRange(row.slot.start_time, row.slot.end_time)}`
                      : ''}
                  </div>
                  <div>
                    <span className="font-medium">Booking ID:</span> {row.booking_id}
                  </div>
                  <div>
                    <span className="font-medium">Marked absent:</span>{' '}
                    {row.marked_absent_at ? formatDateTime(row.marked_absent_at) : '—'}
                  </div>
                </div>

                <div className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
                  absent
                </div>

                <button
                  type="button"
                  onClick={() => handleAllowRebooking(row)}
                  disabled={actingKey === `${row.student.id}-${row.subject}`}
                  className="btn-primary w-full"
                >
                  {actingKey === `${row.student.id}-${row.subject}` ? 'Working...' : 'Allow Rebooking'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
