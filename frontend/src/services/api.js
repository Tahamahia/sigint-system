const API_BASE = '/api'

export async function fetchJSON(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`)
  return res.json()
}

export const api = {
  getSignals: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return fetchJSON(`/signals?${qs}`)
  },
  getRadios: () => fetchJSON('/radios'),
  getRadio: (id) => fetchJSON(`/radios/${id}`),
  getGPSLatest: () => fetchJSON('/gps/latest'),
  getGPSHistory: (radioId) => fetchJSON(`/gps/radio/${radioId}`),
  getTopology: () => fetchJSON('/topology'),
  getSDRDevices: () => fetchJSON('/sdr'),
}
