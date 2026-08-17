import type {
  ConfirmImportFields,
  Driver,
  DriverRoute,
  OfficeLocation,
  OptimizeResponse,
  PendingImport,
  RouteStrategy,
  Settings,
  Store,
  UpdateDriverFields,
  UpdateStoreFields,
} from '../types'

// Strip any trailing slash so a misconfigured env var (e.g. "https://host.com/")
// can't turn "${API_BASE_URL}/api/..." into a double slash — Vercel redirects
// that to the single-slash form, and browsers refuse to follow redirects on
// CORS preflight requests, which silently breaks every API call.
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/+$/, '')

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!response.ok) {
    // FastAPI error bodies are {"detail": "..."} — surface that when present,
    // since it's usually far more useful than the bare status text.
    const body = await response.json().catch(() => null)
    const detail = typeof body?.detail === 'string' ? body.detail : null
    throw new Error(detail ?? `Request to ${path} failed: ${response.status} ${response.statusText}`)
  }
  return response.json() as Promise<T>
}

export const api = {
  quickbooksConnectUrl: `${API_BASE_URL}/api/quickbooks/connect`,
  getStores: () => request<Store[]>('/api/stores'),
  deleteStore: (storeId: string) => request<{ ok: boolean }>(`/api/stores/${storeId}`, { method: 'DELETE' }),
  deleteAllStores: () => request<{ deleted: number }>('/api/stores', { method: 'DELETE' }),
  updateStore: (storeId: string, fields: UpdateStoreFields) =>
    request<Store>(`/api/stores/${storeId}`, { method: 'PUT', body: JSON.stringify(fields) }),
  getDrivers: () => request<Driver[]>('/api/drivers'),
  optimize: (storeIds?: string[], driverIds?: string[]) =>
    request<OptimizeResponse>('/api/optimize', {
      method: 'POST',
      body: JSON.stringify({ store_ids: storeIds ?? null, driver_ids: driverIds ?? null }),
    }),
  uploadImportFile: async (file: File): Promise<{ pending_id: string }> => {
    const formData = new FormData()
    formData.append('file', file)
    // No Content-Type here — the browser sets the multipart boundary itself.
    const response = await fetch(`${API_BASE_URL}/api/imports/upload`, { method: 'POST', body: formData })
    if (!response.ok) {
      const body = await response.json().catch(() => null)
      const detail = typeof body?.detail === 'string' ? body.detail : null
      throw new Error(detail ?? `Upload failed: ${response.status} ${response.statusText}`)
    }
    return response.json()
  },
  getPendingImports: () => request<PendingImport[]>('/api/imports/pending'),
  confirmImport: (pendingId: string, fields: ConfirmImportFields) =>
    request<Store>(`/api/imports/${pendingId}/confirm`, {
      method: 'POST',
      body: JSON.stringify(fields),
    }),
  dismissImport: (pendingId: string) =>
    request<{ ok: boolean }>(`/api/imports/${pendingId}/dismiss`, { method: 'POST' }),
  getOffice: () => request<OfficeLocation>('/api/office'),
  setOffice: (address: string) =>
    request<OfficeLocation>('/api/office', { method: 'PUT', body: JSON.stringify({ address }) }),
  createDriver: (fields: UpdateDriverFields) =>
    request<Driver>('/api/drivers', { method: 'POST', body: JSON.stringify(fields) }),
  updateDriver: (driverId: string, fields: UpdateDriverFields) =>
    request<Driver>(`/api/drivers/${driverId}`, { method: 'PUT', body: JSON.stringify(fields) }),
  deleteDriver: (driverId: string) =>
    request<{ ok: boolean }>(`/api/drivers/${driverId}`, { method: 'DELETE' }),
  getSettings: () => request<Settings>('/api/settings'),
  updateSettings: (settings: Settings) =>
    request<Settings>('/api/settings', { method: 'PUT', body: JSON.stringify(settings) }),
  reorderRoute: (driverId: string, storeIds: string[]) =>
    request<DriverRoute>('/api/routes/reorder', {
      method: 'POST',
      body: JSON.stringify({ driver_id: driverId, store_ids: storeIds }),
    }),
  resequenceRoute: (driverId: string, storeIds: string[], strategy: RouteStrategy) =>
    request<DriverRoute>('/api/routes/resequence', {
      method: 'POST',
      body: JSON.stringify({ driver_id: driverId, store_ids: storeIds, strategy }),
    }),
}
