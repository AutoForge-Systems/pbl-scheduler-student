import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Calendar, Filter, RefreshCw, AlertCircle } from 'lucide-react'
import { slotsService, bookingsService } from '../services/scheduler'
import api from '../services/api'
import { groupSlotsByDate, formatDate } from '../utils/dateUtils'
import LoadingSpinner from '../components/LoadingSpinner'
import Alert from '../components/Alert'
import SlotCard from '../components/SlotCard'
import SlotCardSkeleton from '../components/SlotCardSkeleton'
import { getApiErrorMessage } from '../utils/errorUtils'

export default function AvailableSlots() {
  const navigate = useNavigate()
  const [slots, setSlots] = useState([])
  const [groupedSlots, setGroupedSlots] = useState([])
  const [currentBookings, setCurrentBookings] = useState([])
  const [blockedSubjects, setBlockedSubjects] = useState([])
  const [teacherStatus, setTeacherStatus] = useState(null)
  const [mentorEmails, setMentorEmails] = useState([])
  const [mentors, setMentors] = useState([])
  const [groupId, setGroupId] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isBooking, setIsBooking] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  const [dateFilter, setDateFilter] = useState('')
  const hasLoadedOnceRef = useRef(false)

  // Refresh on focus so newly-marked absences apply quickly
  useEffect(() => {
    function onFocus() {
      loadData({ silent: true })
    }
    window.addEventListener('focus', onFocus)

    // Initial load (and re-load when dateFilter changes)
    loadData({ silent: false })

    const intervalId = setInterval(() => {
      loadData({ silent: true })
    }, 15000)

    return () => {
      window.removeEventListener('focus', onFocus)
      clearInterval(intervalId)
    }
  }, [dateFilter])

  async function loadData({ silent } = { silent: false }) {
    const showLoading = !silent || !hasLoadedOnceRef.current
    if (showLoading) {
      setIsLoading(true)
      setError(null)
    }

    try {
      // Load external student profile (mentorEmails + groupId)
      const profileResp = await api.get('/users/me/external-profile/')
      const mentors = profileResp.data?.mentor_emails || []
      const mentorObjects = profileResp.data?.mentors || []
      const gid = profileResp.data?.group_id || null
      setMentorEmails(Array.isArray(mentors) ? mentors : [])
      setMentors(Array.isArray(mentorObjects) ? mentorObjects : [])
      setGroupId(gid)

      // Load teacher status first to check if they're busy
      const statusData = await slotsService.getTeacherStatus()
      setTeacherStatus(statusData)
      
      // Only load slots if teacher is available
      const params = dateFilter ? { date: dateFilter } : {}
      const [slotsData, bookings, blocked] = await Promise.all([
        slotsService.getAvailable(params),
        bookingsService.getCurrentBooking(),
        bookingsService.getBlockedSubjects()
      ])

      const blockedList = blocked?.blocked_subjects || []
      const blockedSet = new Set(blockedList.map(b => b.subject).filter(Boolean))
      setBlockedSubjects(blockedList)

      const allSlotsRaw = slotsData || []
      const mentorSet = new Set((Array.isArray(mentors) ? mentors : []).map(m => String(m).toLowerCase()))
      const allSlots = mentorSet.size > 0
        ? allSlotsRaw.filter(s => mentorSet.has(String(s?.faculty?.email || '').toLowerCase()))
        : []
      setSlots(allSlots)
      setGroupedSlots(groupSlotsByDate(allSlots))
      setCurrentBookings(Array.isArray(bookings) ? bookings : [])
    } catch (err) {
      console.error('Failed to load slots:', err)
      if (showLoading) {
        setError('Failed to load available slots')
      }
    } finally {
      hasLoadedOnceRef.current = true
      if (showLoading) {
        setIsLoading(false)
      }
    }
  }

  async function handleBook(slot) {
    if (blockedSet.has(slot.subject)) {
      setError(`You were marked absent for ${slot.subject}. Please contact your faculty to book another slot.`)
      return
    }

    const bookedSubjects = new Set(
      currentBookings
        .filter(b => b?.status === 'confirmed')
        .map(b => b?.slot?.subject)
        .filter(Boolean)
    )

    if (bookedSubjects.has(slot.subject)) {
      setError(`You already have an active booking for ${slot.subject}. Cancel it first to book another one.`)
      return
    }

    setIsBooking(true)
    setError(null)
    setSuccess(null)

    try {
      await bookingsService.createBooking(slot.id, groupId)
      setSuccess('Appointment booked successfully!')
      
      // Redirect to booking page after short delay
      setTimeout(() => {
        navigate('/booking')
      }, 1500)
    } catch (err) {
      console.error('Failed to book slot:', err)
      setError(getApiErrorMessage(err, 'Failed to book slot'))
    } finally {
      setIsBooking(false)
    }
  }

  // Check if any teacher is busy
  const anyTeacherBusy = teacherStatus?.any_teacher_busy || false
  const busyTeachers = teacherStatus?.teachers?.filter(t => !t.is_available) || []

  const bookedSubjects = new Set(
    currentBookings
      .filter(b => b?.status === 'confirmed')
      .map(b => b?.slot?.subject)
      .filter(Boolean)
  )

  const blockedSet = new Set(blockedSubjects.map(b => b.subject).filter(Boolean))

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Available Slots</h1>
          <p className="text-gray-600 mt-1">Choose a time slot to book an appointment</p>
        </div>

        <button
          onClick={() => loadData()}
          disabled={isLoading}
          className="btn-secondary inline-flex items-center justify-center gap-2 w-full sm:w-auto"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Mentor Info */}
      {!isLoading && (mentorEmails.length > 0 || mentors.length > 0) && (
        <div className="card p-4">
          <div className="text-sm text-gray-600">Your mentors</div>
          <div className="mt-1 text-gray-900">
            {mentors.length > 0
              ? mentors
                  .map((m) => m?.name || m?.email)
                  .filter(Boolean)
                  .join(', ')
              : mentorEmails.join(', ')}
          </div>
        </div>
      )}

      {/* Teacher Busy Banner */}
      {anyTeacherBusy && !isLoading && (
        <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
          <div className="flex items-start space-x-3">
            <AlertCircle className="w-5 h-5 text-orange-500 mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="font-medium text-orange-800">Teacher Currently Busy</h3>
              <p className="text-orange-700 text-sm mt-1">
                {busyTeachers.length === 1 
                  ? `Your teacher for ${busyTeachers[0].subject} is currently busy.`
                  : 'Some of your assigned teachers are currently busy.'
                }
                {' '}Please check back later for available slots.
              </p>
              {busyTeachers.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {busyTeachers.map((teacher, idx) => (
                    <li key={idx} className="text-sm text-orange-600">
                      • {teacher.teacher_name} ({teacher.subject}) - Busy
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="card p-4">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4">
          <Filter className="w-5 h-5 text-gray-400" />
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 w-full">
            <label htmlFor="date-filter" className="text-sm text-gray-600">
              Filter by date:
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
        </div>
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

      {bookedSubjects.size > 0 && (
        <Alert variant="warning">
          You already have active booking(s) for: {Array.from(bookedSubjects).join(', ')}. You can still book the other subject.
        </Alert>
      )}

      {blockedSubjects.length > 0 && (
        <Alert variant="warning">
          {blockedSubjects.length === 1 ? (
            <span>
              {blockedSubjects[0].detail || (
                <>
                  <strong>{blockedSubjects[0].subject}:</strong> You were marked absent for this subject. Please contact your faculty to book another slot.
                </>
              )}
            </span>
          ) : (
            <span>
              You were marked absent for: {blockedSubjects.map(b => b.subject).join(', ')}. Please contact your faculty to book another slot.
            </span>
          )}
        </Alert>
      )}

      {/* Slots List */}
      {isLoading ? (
        <div>
          <div className="flex items-center justify-center py-3 text-sm text-gray-500">
            <LoadingSpinner size="sm" />
            <span className="ml-2">Loading slots…</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <SlotCardSkeleton key={i} />
            ))}
          </div>
        </div>
      ) : groupedSlots.length === 0 ? (
        <div className="card p-12 text-center">
          <Calendar className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            No Available Slots
          </h3>
          <p className="text-gray-600">
            {blockedSet.size === 2
              ? 'You were marked absent for both subjects. Please contact your faculty.'
              : anyTeacherBusy 
                ? 'Your teacher is currently busy. Please check back later.'
                : dateFilter
                  ? `No slots available for ${formatDate(dateFilter, 'MMMM d, yyyy')}`
                  : 'No slots are currently available. Check back later.'}
          </p>
        </div>
      ) : (
        <div className="space-y-8">
          {groupedSlots.map((group) => (
            <div key={group.date}>
              <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center space-x-2">
                <Calendar className="w-5 h-5 text-primary-600" />
                <span>{group.displayDate}</span>
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {group.slots.map((slot) => (
                  <SlotCard
                    key={slot.id}
                    slot={slot}
                    onBook={handleBook}
                    isBooking={isBooking}
                    isBookedForSubject={bookedSubjects.has(slot.subject)}
                    isBlockedForSubject={blockedSet.has(slot.subject)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
