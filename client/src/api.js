import axios from 'axios'

// Relative to the host, so every call goes through the Vite proxy.
// Never call http://localhost:8001 from the browser: it is not reachable in the sandbox.
const API_BASE_URL = '/api'

export const LEGACY_URL = `${API_BASE_URL}/legacy/`

// Turn an axios error into one sentence a user can act on.
export const errorMessage = err => {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) return detail.map(d => d.msg).join('. ')
  return 'The request did not go through. Check the backend is running on port 8001.'
}

export const api = {
  async getHealth() {
    const response = await axios.get(`${API_BASE_URL}/health`)
    return response.data
  },

  async getSystemsStatus() {
    const response = await axios.get(`${API_BASE_URL}/systems/status`)
    return response.data
  },

  async getDataHealth({ coverage = false, minPolicies = 0 } = {}) {
    const params = new URLSearchParams()
    if (coverage) params.append('coverage', 'true')
    if (minPolicies) params.append('min_policies', String(minPolicies))
    const response = await axios.get(`${API_BASE_URL}/data/health?${params.toString()}`)
    return response.data
  },

  // ---- new policy API, /api/v1 ----
  async getLookups() {
    const response = await axios.get(`${API_BASE_URL}/v1/lookups`)
    return response.data
  },

  async findInsureds(q) {
    const response = await axios.get(`${API_BASE_URL}/v1/insureds`, { params: { q } })
    return response.data
  },

  async priceQuote(payload) {
    const response = await axios.post(`${API_BASE_URL}/v1/quotes/price`, payload)
    return response.data
  },

  async createQuote(payload) {
    const response = await axios.post(`${API_BASE_URL}/v1/quotes`, payload)
    return response.data
  },

  async bindQuote(policyRef, payload = {}) {
    const response = await axios.post(`${API_BASE_URL}/v1/quotes/${policyRef}/bind`, payload)
    return response.data
  },

  async getPolicies(filters = {}) {
    const params = new URLSearchParams()
    if (filters.q) params.append('q', filters.q)
    if (filters.status && filters.status !== 'all') params.append('status', filters.status)
    const response = await axios.get(`${API_BASE_URL}/v1/policies?${params.toString()}`)
    return response.data
  },

  async getPolicy(policyRef) {
    const response = await axios.get(`${API_BASE_URL}/v1/policies/${policyRef}`)
    return response.data
  },

  async previewAdjustment(policyRef, payload) {
    const response = await axios.post(`${API_BASE_URL}/v1/policies/${policyRef}/adjustments/preview`, payload)
    return response.data
  },

  async applyAdjustment(policyRef, payload) {
    const response = await axios.post(`${API_BASE_URL}/v1/policies/${policyRef}/adjustments`, payload)
    return response.data
  }
}
