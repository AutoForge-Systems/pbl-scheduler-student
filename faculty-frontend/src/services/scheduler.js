import api from './api'

export const slotsService = {
  // Get all faculty's slots
  getMySlots: async (params = {}) => {
    const response = await api.get('/slots/faculty/', { params })
    return response.data
  },

  // Get faculty subject (derived from existing slots)
  getMySubject: async () => {
    const response = await api.get('/slots/faculty/subject/')
    return response.data
  },

  // Get single slot
  getById: async (id) => {
    const response = await api.get(`/slots/faculty/${id}/`)
    return response.data
  },

  // Create new slot (single)
  createSlot: async (data) => {
    const response = await api.post('/slots/faculty/', data)
    return response.data
  },

  // Bulk create slots with auto-generation
  bulkCreateSlots: async (data) => {
    const response = await api.post('/slots/faculty/bulk-create/', data)
    return response.data
  },

  // Update slot
  updateSlot: async (id, data) => {
    const response = await api.put(`/slots/faculty/${id}/`, data)
    return response.data
  },

  // Delete slot
  deleteSlot: async (id) => {
    await api.delete(`/slots/faculty/${id}/`)
  },

  // Delete all of today's slots (atomic)
  deleteTodaysSlots: async () => {
    const response = await api.delete('/slots/faculty/delete-todays-slots/')
    return response.data
  },

  // Get current availability status
  getAvailability: async () => {
    const response = await api.get('/slots/faculty/availability/')
    return response.data
  },

  // Set availability status (busy/free)
  setAvailability: async (isAvailable) => {
    const response = await api.post('/slots/faculty/availability/', {
      is_available: isAvailable
    })
    return response.data
  }
}

export const bookingsService = {
  // Get all bookings on faculty's slots
  getBookings: async (params = {}) => {
    const response = await api.get('/bookings/faculty/', { params })
    return response.data
  },

  // Get single booking
  getById: async (id) => {
    const response = await api.get(`/bookings/faculty/${id}/`)
    return response.data
  },

  // Cancel a booking on a faculty slot (override)
  cancelBooking: async (id, reason = '') => {
    const response = await api.patch(`/faculty/bookings/${id}/cancel`, { reason })
    return response.data
  },

  // Mark a booking as completed (evaluated)
  completeBooking: async (id) => {
    // Required endpoint
    const response = await api.patch(`/faculty/bookings/${id}/mark-completed`)
    return response.data
  },

  // Mark a booking as absent
  markAbsent: async (id) => {
    // Required endpoint
    const response = await api.patch(`/faculty/bookings/${id}/mark-absent`)
    return response.data
  },

  // List absent students (for this faculty)
  getAbsentStudents: async () => {
    const response = await api.get('/faculty/absent-students')
    return response.data
  },

  // Allow rebooking for a specific absent booking (faculty-owned)
  allowRebooking: async ({ bookingId }) => {
    const response = await api.post(`/faculty/absent/${bookingId}/allow-rebook/`)
    return response.data
  }
}
