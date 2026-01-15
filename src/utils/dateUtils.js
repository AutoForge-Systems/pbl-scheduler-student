import { format, parseISO, formatDistanceToNow } from 'date-fns'

/**
 * Format a date string to display format
 */
export function formatDate(dateString, formatStr = 'MMM d, yyyy') {
  if (!dateString) return ''
  const date = typeof dateString === 'string' ? parseISO(dateString) : dateString
  return format(date, formatStr)
}

/**
 * Format a date string to time
 */
export function formatTime(dateString, formatStr = 'h:mm a') {
  if (!dateString) return ''
  const date = typeof dateString === 'string' ? parseISO(dateString) : dateString
  return format(date, formatStr)
}

/**
 * Format date and time together
 */
export function formatDateTime(dateString) {
  if (!dateString) return ''
  const date = typeof dateString === 'string' ? parseISO(dateString) : dateString
  return format(date, 'MMM d, yyyy h:mm a')
}

/**
 * Format time range
 */
export function formatTimeRange(startTime, endTime) {
  return `${formatTime(startTime)} - ${formatTime(endTime)}`
}

/**
 * Get relative time (e.g., "in 2 hours")
 */
export function getRelativeTime(dateString) {
  if (!dateString) return ''
  const date = typeof dateString === 'string' ? parseISO(dateString) : dateString
  return formatDistanceToNow(date, { addSuffix: true })
}

/**
 * Check if a date is in the past
 */
export function isPast(dateString) {
  if (!dateString) return false
  const date = typeof dateString === 'string' ? parseISO(dateString) : dateString
  return date < new Date()
}

/**
 * Check if a date is today
 */
export function isToday(dateString) {
  if (!dateString) return false
  const date = typeof dateString === 'string' ? parseISO(dateString) : dateString
  const today = new Date()
  return (
    date.getDate() === today.getDate() &&
    date.getMonth() === today.getMonth() &&
    date.getFullYear() === today.getFullYear()
  )
}

/**
 * Group slots by date
 */
export function groupSlotsByDate(slots) {
  const grouped = {}
  
  slots.forEach(slot => {
    const dateKey = formatDate(slot.start_time, 'yyyy-MM-dd')
    if (!grouped[dateKey]) {
      grouped[dateKey] = {
        date: dateKey,
        displayDate: formatDate(slot.start_time, 'EEEE, MMMM d'),
        slots: []
      }
    }
    grouped[dateKey].slots.push(slot)
  })
  
  return Object.values(grouped).sort((a, b) => a.date.localeCompare(b.date))
}
