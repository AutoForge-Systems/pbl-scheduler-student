export function getApiErrorMessage(err, fallback = 'Request failed') {
  const data = err?.response?.data

  if (!data) return fallback

  // Common DRF / custom formats
  if (typeof data === 'string') return data
  if (typeof data?.detail === 'string') return data.detail

  // Custom exception handler shape: { success:false, error:{ code, message, details } }
  if (typeof data?.error?.message === 'string') return data.error.message
  if (typeof data?.error === 'string') return data.error

  // Field errors: { field: ['msg'] }
  if (typeof data === 'object') {
    const firstKey = Object.keys(data)[0]
    if (firstKey) {
      const v = data[firstKey]
      if (Array.isArray(v) && typeof v[0] === 'string') return v[0]
      if (typeof v === 'string') return v
    }

    try {
      return JSON.stringify(data)
    } catch {
      return fallback
    }
  }

  return fallback
}
