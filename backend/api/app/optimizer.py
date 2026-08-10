from .geo import haversine_km
from .models import Driver, DriverRoute, RouteStop, Store
from .routing import get_route_metrics
from .time_utils import format_minutes, parse_hhmm

# Rough estimate of how long unloading/check-in takes at a stop: a fixed
# base (parking, paperwork) plus a per-case handling time. Tune against real
# operations data — this is a placeholder, not a measured figure.
SERVICE_TIME_BASE_MIN = 5.0
SERVICE_TIME_PER_CASE_MIN = 1.5


def service_minutes(case_count: int) -> float:
    return SERVICE_TIME_BASE_MIN + SERVICE_TIME_PER_CASE_MIN * case_count


def nearest_neighbor_order(start_coords, stores: list[Store]) -> list[Store]:
    remaining = stores.copy()
    ordered: list[Store] = []
    current = start_coords
    while remaining:
        nearest = min(remaining, key=lambda s: haversine_km(current, s.coordinates))
        ordered.append(nearest)
        remaining.remove(nearest)
        current = nearest.coordinates
    return ordered


def build_routes(
    drivers: list[Driver], stores: list[Store]
) -> tuple[list[DriverRoute], list[str]]:
    """Naive placeholder optimizer.

    Round-robins stores across drivers by current load, then orders each
    driver's stops with nearest-neighbor. Ignores time windows, traffic, and
    proper multi-constraint capacity packing — this is a stand-in for a real
    Vehicle Routing Problem solver (e.g. Google OR-Tools' routing module),
    not a production optimizer.

    Driving times/distances and the route geometry come from OSRM (see
    routing.py) for whatever stop order this function picks — OSRM is not
    used to choose the order itself.
    """
    if not drivers:
        return [], [s.id for s in stores]

    assignments: dict[str, list[Store]] = {d.id: [] for d in drivers}
    loads: dict[str, int] = {d.id: 0 for d in drivers}
    unassigned: list[str] = []

    for store in stores:
        driver = min(drivers, key=lambda d: loads[d.id])
        if loads[driver.id] + store.case_count > driver.vehicle_capacity_cases:
            unassigned.append(store.id)
            continue
        assignments[driver.id].append(store)
        loads[driver.id] += store.case_count

    routes: list[DriverRoute] = []
    for driver in drivers:
        ordered = nearest_neighbor_order(driver.depot, assignments[driver.id])
        routes.append(build_route_for_order(driver, ordered))

    return routes, unassigned


def build_route_for_order(driver: Driver, ordered: list[Store]) -> DriverRoute:
    """Computes a DriverRoute's timing/distance metrics for a stop order
    that's already been decided -- shared by build_routes (which picks the
    order itself via nearest_neighbor_order) and manual stop reordering
    (routers/routes.py's /routes/reorder), which hands in a user-picked
    order instead."""
    metrics = get_route_metrics(driver.depot, ordered)

    stops: list[RouteStop] = []
    cumulative_min = float(parse_hhmm(driver.shift_start))
    total_drive_min = 0.0
    total_service_min = 0.0

    for i, store in enumerate(ordered):
        drive_min = metrics.leg_durations_min[i]
        cumulative_min += drive_min
        eta = format_minutes(cumulative_min)
        window_start = parse_hhmm(store.time_window_start)
        window_end = parse_hhmm(store.time_window_end)
        on_time = window_start <= cumulative_min <= window_end

        stop_service_min = service_minutes(store.case_count)

        stops.append(
            RouteStop(
                store=store,
                sequence=i + 1,
                eta=eta,
                drive_minutes=round(drive_min, 1),
                service_minutes=round(stop_service_min, 1),
                on_time=on_time,
            )
        )

        cumulative_min += stop_service_min
        total_drive_min += drive_min
        total_service_min += stop_service_min

    total_distance_km = sum(metrics.leg_distances_km)

    return DriverRoute(
        driver=driver,
        stops=stops,
        total_distance_km=round(total_distance_km, 2),
        total_drive_minutes=round(total_drive_min, 1),
        total_service_minutes=round(total_service_min, 1),
        estimated_finish_time=format_minutes(cumulative_min),
        estimate_source=metrics.estimate_source,
        geometry=metrics.geometry,
    )
