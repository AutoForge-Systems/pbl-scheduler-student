import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Calendar, Clock, ArrowLeft, Plus, Timer, Coffee } from 'lucide-react'
import { slotsService } from '../services/scheduler'
import Alert from '../components/Alert'

// Slot duration options (in minutes)
const SLOT_DURATIONS = [
  { value: 5, label: '5 minutes' },
  { value: 10, label: '10 minutes' },
  { value: 15, label: '15 minutes' }
]

// Break duration options (in minutes)
const BREAK_DURATIONS = [
  { value: 0, label: 'No break' },
  { value: 5, label: '5 minutes' },
  { value: 10, label: '10 minutes' },
  { value: 15, label: '15 minutes' }
]

export default function CreateSlot() {
  const navigate = useNavigate()
  const [formData, setFormData] = useState({
    date: '',
    startTime: '',
    endTime: '',
    slotDuration: '',
    breakDuration: ''
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [previewSlots, setPreviewSlots] = useState([])

  function handleChange(e) {
    const { name, value } = e.target
    setFormData(prev => {
      const newData = { ...prev, [name]: value }
      // Update preview when relevant fields change
      if (['startTime', 'endTime', 'slotDuration', 'breakDuration'].includes(name)) {
        updatePreview(newData)
      }
      return newData
    })
  }

  function updatePreview(data) {
    const { startTime, endTime, slotDuration, breakDuration } = data
    
    if (!startTime || !endTime || !slotDuration || breakDuration === '') {
      setPreviewSlots([])
      return
    }

    const slots = []
    const [startH, startM] = startTime.split(':').map(Number)
    const [endH, endM] = endTime.split(':').map(Number)
    
    let currentMinutes = startH * 60 + startM
    const endMinutes = endH * 60 + endM
    const duration = parseInt(slotDuration)
    const breakTime = parseInt(breakDuration)

    let slotNumber = 1
    while (currentMinutes + duration <= endMinutes) {
      const slotStart = formatMinutesToTime(currentMinutes)
      const slotEnd = formatMinutesToTime(currentMinutes + duration)
      slots.push({
        number: slotNumber,
        start: slotStart,
        end: slotEnd
      })
      currentMinutes += duration + breakTime
      slotNumber++
    }

    setPreviewSlots(slots)
  }

  function formatMinutesToTime(minutes) {
    const h = Math.floor(minutes / 60)
    const m = minutes % 60
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)

    // Validate all fields
    if (!formData.date || !formData.startTime || 
        !formData.endTime || !formData.slotDuration || formData.breakDuration === '') {
      setError('Please fill in all fields')
      return
    }

    // Combine date and time into ISO format
    const startDateTime = new Date(`${formData.date}T${formData.startTime}`)
    const endDateTime = new Date(`${formData.date}T${formData.endTime}`)

    // Validate times
    if (endDateTime <= startDateTime) {
      setError('End time must be after start time')
      return
    }

    if (startDateTime <= new Date()) {
      setError('Start time must be in the future')
      return
    }

    // Check that at least one slot can be generated
    if (previewSlots.length === 0) {
      setError('Time range is too short to create any slots with the selected duration')
      return
    }

    setIsSubmitting(true)

    try {
      const result = await slotsService.bulkCreateSlots({
        start_time: startDateTime.toISOString(),
        end_time: endDateTime.toISOString(),
        slot_duration: parseInt(formData.slotDuration),
        break_duration: parseInt(formData.breakDuration)
      })

      navigate('/slots', { 
        state: { success: `Successfully created ${result.slots_count} slots!` } 
      })
    } catch (err) {
      console.error('Failed to create slots:', err)
      const message = err.response?.data?.error ||
                      err.response?.data?.detail ||
                      err.response?.data?.non_field_errors?.[0] ||
                      'Failed to create slots'
      setError(message)
    } finally {
      setIsSubmitting(false)
    }
  }

  // Get today's date in YYYY-MM-DD format for min attribute
  const today = new Date().toISOString().split('T')[0]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-3">
        <Link
          to="/slots"
          className="h-11 w-11 inline-flex items-center justify-center hover:bg-gray-100 rounded-lg transition-colors flex-shrink-0"
        >
          <ArrowLeft className="w-5 h-5 text-gray-600" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Create Schedule</h1>
          <p className="text-gray-600 mt-1">
            Set your availability with auto-generated time slots
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Form */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Schedule Configuration</h2>
          
          {error && (
            <Alert variant="error" onClose={() => setError(null)} className="mb-6">
              {error}
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Date */}
            <div>
              <label htmlFor="date" className="block text-sm font-medium text-gray-700 mb-2">
                <div className="flex items-center space-x-2">
                  <Calendar className="w-4 h-4" />
                  <span>Date</span>
                  <span className="text-red-500">*</span>
                </div>
              </label>
              <input
                type="date"
                id="date"
                name="date"
                value={formData.date}
                onChange={handleChange}
                min={today}
                className="input"
                required
              />
            </div>

            {/* Time Range */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label htmlFor="startTime" className="block text-sm font-medium text-gray-700 mb-2">
                  <div className="flex items-center space-x-2">
                    <Clock className="w-4 h-4" />
                    <span>Start Time</span>
                    <span className="text-red-500">*</span>
                  </div>
                </label>
                <input
                  type="time"
                  id="startTime"
                  name="startTime"
                  value={formData.startTime}
                  onChange={handleChange}
                  className="input"
                  required
                />
              </div>

              <div>
                <label htmlFor="endTime" className="block text-sm font-medium text-gray-700 mb-2">
                  <div className="flex items-center space-x-2">
                    <Clock className="w-4 h-4" />
                    <span>End Time</span>
                    <span className="text-red-500">*</span>
                  </div>
                </label>
                <input
                  type="time"
                  id="endTime"
                  name="endTime"
                  value={formData.endTime}
                  onChange={handleChange}
                  className="input"
                  required
                />
              </div>
            </div>

            {/* Slot Duration */}
            <div>
              <label htmlFor="slotDuration" className="block text-sm font-medium text-gray-700 mb-2">
                <div className="flex items-center space-x-2">
                  <Timer className="w-4 h-4" />
                  <span>Slot Duration</span>
                  <span className="text-red-500">*</span>
                </div>
              </label>
              <select
                id="slotDuration"
                name="slotDuration"
                value={formData.slotDuration}
                onChange={handleChange}
                className="input"
                required
              >
                <option value="">Select duration</option>
                {SLOT_DURATIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              <p className="text-xs text-gray-500 mt-1">
                Duration of each individual slot
              </p>
            </div>

            {/* Break Duration */}
            <div>
              <label htmlFor="breakDuration" className="block text-sm font-medium text-gray-700 mb-2">
                <div className="flex items-center space-x-2">
                  <Coffee className="w-4 h-4" />
                  <span>Break Between Slots</span>
                  <span className="text-red-500">*</span>
                </div>
              </label>
              <select
                id="breakDuration"
                name="breakDuration"
                value={formData.breakDuration}
                onChange={handleChange}
                className="input"
                required
              >
                <option value="">Select break duration</option>
                {BREAK_DURATIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              <p className="text-xs text-gray-500 mt-1">
                Gap between consecutive slots
              </p>
            </div>

            {/* Submit */}
            <div className="flex flex-col sm:flex-row gap-3 pt-2">
              <Link to="/slots" className="btn-secondary w-full sm:flex-1 text-center">
                Cancel
              </Link>
              <button
                type="submit"
                disabled={isSubmitting || previewSlots.length === 0}
                className="btn-primary w-full sm:flex-1 flex items-center justify-center space-x-2"
              >
                <Plus className="w-4 h-4" />
                <span>
                  {isSubmitting 
                    ? 'Creating...' 
                    : `Create ${previewSlots.length} Slot${previewSlots.length !== 1 ? 's' : ''}`
                  }
                </span>
              </button>
            </div>
          </form>
        </div>

        {/* Preview Panel */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Slots Preview</h2>
          
          {previewSlots.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <Timer className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>Configure your schedule to see the preview</p>
              <p className="text-sm mt-1">Select time range, slot duration, and break</p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-600">
                  {previewSlots.length} slot{previewSlots.length !== 1 ? 's' : ''} will be created
                </span>
                {formData.breakDuration && parseInt(formData.breakDuration) > 0 && (
                  <span className="text-gray-500">
                    {formData.breakDuration} min break between slots
                  </span>
                )}
              </div>
              
              <div className="max-h-[400px] overflow-y-auto space-y-2">
                {previewSlots.map((slot) => (
                  <div 
                    key={slot.number}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-100"
                  >
                    <div className="flex items-center space-x-3">
                      <span className="w-8 h-8 flex items-center justify-center bg-primary-100 text-primary-700 rounded-full text-sm font-medium">
                        {slot.number}
                      </span>
                      <div>
                        <span className="font-medium text-gray-900">
                          {slot.start} - {slot.end}
                        </span>
                        <span className="text-sm text-gray-500 ml-2">
                          ({formData.slotDuration} min)
                        </span>
                      </div>
                    </div>
                    <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded">
                      Available
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Tips */}
      <div className="card p-6">
        <h3 className="font-medium text-gray-900 mb-3">Tips</h3>
        <ul className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm text-gray-600">
          <li className="flex items-start space-x-2">
            <span className="text-primary-600">•</span>
            <span>Slots are auto-generated based on your configuration</span>
          </li>
          <li className="flex items-start space-x-2">
            <span className="text-primary-600">•</span>
            <span>Students only see slots for their assigned subject</span>
          </li>
          <li className="flex items-start space-x-2">
            <span className="text-primary-600">•</span>
            <span>Overlapping slots with existing ones are skipped</span>
          </li>
          <li className="flex items-start space-x-2">
            <span className="text-primary-600">•</span>
            <span>Use the Shift Schedule feature to delay slots if needed</span>
          </li>
        </ul>
      </div>
    </div>
  )
}
