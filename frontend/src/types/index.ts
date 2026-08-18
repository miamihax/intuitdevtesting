export interface Coordinates {
  lat: number
  lng: number
}

export interface Store {
  id: string
  name: string
  address: string
  coordinates: Coordinates
  time_window_start: string
  time_window_end: string
  case_count: number
  approximate_location: boolean
  invoice_number: string | null
}

export interface Driver {
  id: string
  name: string
  depot: Coordinates
  vehicle_capacity_cases: number
  shift_start: string
  shift_end: string
}

export interface RouteStop {
  store: Store
  sequence: number
  eta: string | null
  drive_minutes: number | null
  service_minutes: number | null
  on_time: boolean | null
}

export interface DriverRoute {
  driver: Driver
  stops: RouteStop[]
  total_distance_km: number
  total_drive_minutes: number
  total_service_minutes: number
  estimated_finish_time: string
  /** "road_network": real OSRM driving times (no live traffic). "straight_line_estimate": OSRM was unreachable. */
  estimate_source: 'road_network' | 'straight_line_estimate'
  geometry: [number, number][] | null
}

export type RouteStrategy = 'fastest' | 'time_windows'

export interface OptimizeResponse {
  routes: DriverRoute[]
  unassigned_store_ids: string[]
}

export interface PendingImport {
  id: string
  file_name: string
  status: 'processing' | 'ready' | 'error'
  source: 'upload' | 'quickbooks'
  invoice_number: string | null
  name: string | null
  address: string | null
  coordinates: Coordinates | null
  approximate_location: boolean
  suggested_address: string | null
  suggested_address_source: 'bill_to' | 'web_search' | null
  case_count: number | null
  time_window_start: string | null
  time_window_end: string | null
  error: string | null
}

export interface ConfirmImportFields {
  name: string
  address: string
  time_window_start: string
  time_window_end: string
  case_count: number
}

export interface OfficeLocation {
  address: string | null
  coordinates: Coordinates
}

export interface UpdateDriverFields {
  name: string
  vehicle_capacity_cases: number
  shift_start: string
  shift_end: string
}

export interface UpdateStoreFields {
  name: string
  address: string
  time_window_start: string
  time_window_end: string
  case_count: number
}

export interface Settings {
  auto_add_imports: boolean
  distance_unit: 'mi' | 'km'
  time_format: '24h' | '12h'
  theme: 'dark' | 'light'
}
