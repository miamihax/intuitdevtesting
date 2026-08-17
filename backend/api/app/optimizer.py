from .models import Driver, DriverRoute, RouteStop, Store
from .routing import get_duration_distance_matrix, get_route_metrics
from .time_utils import format_minutes, parse_hhmm

# Rough estimate of how long unloading/check-in takes at a stop: a fixed
# base (parking, paperwork) plus a per-case handling time. Tune against real
# operations data — this is a placeholder, not a measured figure.
SERVICE_TIME_BASE_MIN = 5.0
SERVICE_TIME_PER_CASE_MIN = 1.5

# 2-opt refinement is O(n^2) per pass and repeats until no swap helps: fine
# for realistic per-driver stop counts, but skip it above this size so one
# oversized route can't stall the whole /optimize request.
MAX_TWO_OPT_STOPS = 40


def service_minutes(case_count: int) -> float:
    return SERVICE_TIME_BASE_MIN + SERVICE_TIME_PER_CASE_MIN * case_count


def _total_duration(order: list[int], duration_min: list[list[float]]) -> float:
    total = 0.0
    prev_matrix_idx = 0
    for i in order:
        total += duration_min[prev_matrix_idx][i + 1]
        prev_matrix_idx = i + 1
    return total


def _evaluate_order(
    order: list[int],
    stores: list[Store],
    duration_min: list[list[float]],
    shift_start_min: float,
) -> tuple[int, float, float]:
    """Scores a candidate order as (# stops visited past their time window,
    total minutes of lateness, total drive minutes) -- compared
    lexicographically, so honoring time windows always wins first, then
    least total lateness, then fastest/shortest drive time."""
    cumulative_min = shift_start_min
    prev_matrix_idx = 0
    late_count = 0
    total_lateness = 0.0
    total_duration = 0.0
    for i in order:
        leg = duration_min[prev_matrix_idx][i + 1]
        cumulative_min += leg
        total_duration += leg
        window_end = parse_hhmm(stores[i].time_window_end)
        if cumulative_min > window_end:
            late_count += 1
            total_lateness += cumulative_min - window_end
        cumulative_min += service_minutes(stores[i].case_count)
        prev_matrix_idx = i + 1
    return late_count, total_lateness, total_duration


def _construct_time_window_aware_order(
    stores: list[Store],
    duration_min: list[list[float]],
    shift_start_min: float,
) -> list[int]:
    """Greedy construction: repeatedly visits the nearest-by-drive-time
    remaining stop whose time window can still be met from the current
    cumulative time. If none can be met anymore, visits whichever window
    closes soonest next, to limit cascading lateness rather than compound
    it. Returns store indices (into `stores`) in visit order."""
    remaining = list(range(len(stores)))
    order: list[int] = []
    current_matrix_idx = 0  # depot
    cumulative_min = shift_start_min

    while remaining:
        feasible = [
            i
            for i in remaining
            if cumulative_min + duration_min[current_matrix_idx][i + 1]
            <= parse_hhmm(stores[i].time_window_end)
        ]
        if feasible:
            next_i = min(feasible, key=lambda i: duration_min[current_matrix_idx][i + 1])
        else:
            next_i = min(remaining, key=lambda i: parse_hhmm(stores[i].time_window_end))

        cumulative_min += duration_min[current_matrix_idx][next_i + 1]
        cumulative_min += service_minutes(stores[next_i].case_count)
        order.append(next_i)
        remaining.remove(next_i)
        current_matrix_idx = next_i + 1

    return order


def _two_opt_improve(
    order: list[int],
    stores: list[Store],
    duration_min: list[list[float]],
    shift_start_min: float,
) -> list[int]:
    """Local search over the constructed order: repeatedly tries reversing
    segments (2-opt), keeping a reversal only if it scores strictly better
    under _evaluate_order -- i.e. it never trades away time-window
    adherence for a shorter/faster route, only improves distance/time
    within (or further into) window-feasible orderings."""
    if len(order) > MAX_TWO_OPT_STOPS:
        return order

    best = order
    best_score = _evaluate_order(best, stores, duration_min, shift_start_min)
    n = len(order)
    improved = True
    while improved and n > 3:
        improved = False
        for i in range(n - 1):
            for j in range(i + 1, n):
                candidate = best[:i] + best[i : j + 1][::-1] + best[j + 1 :]
                score = _evaluate_order(candidate, stores, duration_min, shift_start_min)
                if score < best_score:
                    best, best_score = candidate, score
                    improved = True
    return best


def _two_opt_minimize_duration(order: list[int], duration_min: list[list[float]]) -> list[int]:
    """Same local search as _two_opt_improve, but scores purely on total
    drive time -- used by fastest_order, which ignores time windows
    entirely."""
    if len(order) > MAX_TWO_OPT_STOPS:
        return order

    best = order
    best_total = _total_duration(best, duration_min)
    n = len(order)
    improved = True
    while improved and n > 3:
        improved = False
        for i in range(n - 1):
            for j in range(i + 1, n):
                candidate = best[:i] + best[i : j + 1][::-1] + best[j + 1 :]
                total = _total_duration(candidate, duration_min)
                if total < best_total:
                    best, best_total = candidate, total
                    improved = True
    return best


def optimize_stop_order(driver: Driver, stores: list[Store]) -> list[Store]:
    """Orders one driver's stops factoring in time windows, real driving
    distance, and real driving time together: a greedy nearest-feasible-
    window construction over an OSRM duration/distance matrix (falling back
    to a straight-line/assumed-speed matrix if OSRM is unreachable),
    refined by 2-opt local search. This is the ordering strategy used for
    initial route creation (see build_routes) and for the "time_windows"
    manual resequence strategy.
    """
    if len(stores) <= 1:
        return list(stores)

    duration_min, _distance_km, _source = get_duration_distance_matrix(driver.depot, stores)
    shift_start_min = float(parse_hhmm(driver.shift_start))

    order = _construct_time_window_aware_order(stores, duration_min, shift_start_min)
    order = _two_opt_improve(order, stores, duration_min, shift_start_min)
    return [stores[i] for i in order]


def fastest_order(driver: Driver, stores: list[Store]) -> list[Store]:
    """Pure nearest-neighbor-by-real-drive-time construction, refined by
    2-opt to minimize total driving time -- ignores time windows entirely.
    Used by the "fastest" manual resequence strategy; initial route
    creation uses optimize_stop_order instead, which weighs windows too.
    """
    if len(stores) <= 1:
        return list(stores)

    duration_min, _distance_km, _source = get_duration_distance_matrix(driver.depot, stores)
    remaining = list(range(len(stores)))
    order: list[int] = []
    current_matrix_idx = 0
    while remaining:
        next_i = min(remaining, key=lambda i: duration_min[current_matrix_idx][i + 1])
        order.append(next_i)
        remaining.remove(next_i)
        current_matrix_idx = next_i + 1

    order = _two_opt_minimize_duration(order, duration_min)
    return [stores[i] for i in order]


def order_for_strategy(strategy: str, driver: Driver, stores: list[Store]) -> list[Store]:
    if strategy == "time_windows":
        return optimize_stop_order(driver, stores)
    return fastest_order(driver, stores)


def build_routes(
    drivers: list[Driver], stores: list[Store]
) -> tuple[list[DriverRoute], list[str]]:
    """Assigns stores to drivers, then orders each driver's stops with
    optimize_stop_order (time windows + real driving distance/time).

    Assignment is still a simple round-robin by current load/capacity, not
    a joint optimization over which driver should take which stop -- this
    is a stand-in for a real Vehicle Routing Problem solver (e.g. Google
    OR-Tools' routing module), not a production optimizer. Only the
    per-driver stop order is genuinely optimized.

    Driving times/distances and the route geometry ultimately shown to the
    user come from OSRM (see routing.py) for whatever stop order this
    function picks.
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
        ordered = optimize_stop_order(driver, assignments[driver.id])
        routes.append(build_route_for_order(driver, ordered))

    return routes, unassigned


def build_route_for_order(driver: Driver, ordered: list[Store]) -> DriverRoute:
    """Computes a DriverRoute's timing/distance metrics for a stop order
    that's already been decided -- shared by build_routes (which picks the
    order itself via optimize_stop_order) and manual stop reordering
    (routers/routes.py's /routes/reorder and /routes/resequence), which
    hand in a user-picked or strategy-picked order instead."""
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
