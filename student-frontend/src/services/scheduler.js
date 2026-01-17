import api from './api'

export const slotsService = {
  // Get all available slots
  getAvailable: async (params = {}) => {
    const response = await api.get('/slots/available/', { params })
    return response.data
  },

  // Get single slot
  getById: async (id) => {
    const response = await api.get(`/slots/available/${id}/`)
    return response.data
  },

  // Get teacher availability status
  getTeacherStatus: async () => {
    const response = await api.get('/slots/available/teacher-status/')
    return response.data
  }
}

export const bookingsService = {
  // Get student's bookings
  getMyBookings: async (params = {}) => {
    const response = await api.get('/bookings/student/', { params })
    return response.data
  },

  // Get current active bookings (max 2: one per subject)
  getCurrentBooking: async () => {
    const response = await api.get('/bookings/student/current/')
    return response.data
  },

  // Get subjects blocked due to absence (no rebooking permission)
  getBlockedSubjects: async () => {
    const response = await api.get('/bookings/student/blocked-subjects/')
    return response.data
  },

  // Create booking
  createBooking: async (slotId) => {
    const response = await api.post('/bookings/student/', { slot_id: slotId })
    return response.data
  },

  // Cancel booking
  cancelBooking: async (bookingId, reason = '') => {
    const response = await api.post(`/bookings/student/${bookingId}/cancel/`, { reason })
    return response.data
  }
}
