from pydantic import BaseModel


class Coordinates(BaseModel):
    lat: float
    lng: float


class Store(BaseModel):
    id: str
    name: str
    address: str
    coordinates: Coordinates
    time_window_start: str  # "09:00"
    time_window_end: str  # "17:00"
    case_count: int  # cases of liquor to deliver
    approximate_location: bool = False  # True if geocoding fell back to a ZIP-code centroid


class Driver(BaseModel):
    id: str
    name: str
    depot: Coordinates
    vehicle_capacity_cases: int
    shift_start: str
    shift_end: str


class RouteStop(BaseModel):
    store: Store
    sequence: int
    eta: str | None = None  # "HH:MM" clock time the driver is expected to arrive
    drive_minutes: float | None = None  # driving time from the previous stop
    service_minutes: float | None = None  # estimated unload/check-in time at this stop
    on_time: bool | None = None  # whether the ETA falls within the store's time window


class DriverRoute(BaseModel):
    driver: Driver
    stops: list[RouteStop]
    total_distance_km: float
    total_drive_minutes: float
    total_service_minutes: float
    estimated_finish_time: str  # "HH:MM" — when the driver is expected to complete the route
    # "road_network": real driving times from OSRM (no live traffic — see routing.py).
    # "straight_line_estimate": OSRM was unreachable; distance/speed-based fallback.
    estimate_source: str
    geometry: list[list[float]] | None = None  # road-snapped [lng, lat] path, depot through all stops


class OptimizeRequest(BaseModel):
    store_ids: list[str] | None = None  # None = use all stores
    driver_ids: list[str] | None = None  # None = use all drivers


class OptimizeResponse(BaseModel):
    routes: list[DriverRoute]
    unassigned_store_ids: list[str]


class ReorderRouteRequest(BaseModel):
    driver_id: str
    store_ids: list[str]  # this driver's stops, in the desired new order


class AgentAskRequest(BaseModel):
    question: str


class AgentAskResponse(BaseModel):
    answer: str


class PendingImport(BaseModel):
    id: str
    file_name: str
    status: str = "processing"  # "processing" | "ready" | "error"
    source: str = "upload"  # "upload" (OCR'd file) | "quickbooks" (webhook-pushed invoice)
    invoice_number: str | None = None
    name: str | None = None  # OCR-extracted or QuickBooks customer/location name
    address: str | None = None
    coordinates: Coordinates | None = None  # geocoded from `address`, if found
    approximate_location: bool = False  # True if geocoding fell back to a ZIP-code centroid
    case_count: int | None = None  # pre-filled from QuickBooks line-item quantities, if available
    time_window_start: str | None = None  # OCR-extracted from a delivery note, if present
    time_window_end: str | None = None
    error: str | None = None


class ConfirmImportRequest(BaseModel):
    name: str
    address: str
    time_window_start: str = "09:00"
    time_window_end: str = "17:00"
    case_count: int = 0


class OfficeLocation(BaseModel):
    address: str | None = None  # None until explicitly set — coordinates still have a default
    coordinates: Coordinates


class SetOfficeRequest(BaseModel):
    address: str


class Settings(BaseModel):
    # When set, imports (upload/OCR) skip manual review and are confirmed
    # into an order automatically as soon as they finish processing --
    # only when enough was extracted to do so (name, address, and a
    # geocode); anything short of that still falls back to manual review.
    auto_add_imports: bool = False


class UpdateDriverRequest(BaseModel):
    name: str
    vehicle_capacity_cases: int
    shift_start: str
    shift_end: str
