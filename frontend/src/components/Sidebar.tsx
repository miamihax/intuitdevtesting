import { useState } from 'react'
import type { Driver, DriverRoute, RouteStrategy, Store } from '../types'

const KM_TO_MI = 0.621371

// Converts a decimal minute value (e.g. 45.3) into "1h 45m 18s" instead of
// showing the raw fraction — omits the hours part when there aren't any.
function formatDuration(totalMinutes: number): string {
  const totalSeconds = Math.round(totalMinutes * 60)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  return hours > 0 ? `${hours}h ${minutes}m ${seconds}s` : `${minutes}m ${seconds}s`
}

// total_distance_km is always computed/transmitted in km (see backend
// models.py) -- convert for display only, based on the user's preference.
function formatDistance(km: number, unit: 'mi' | 'km'): string {
  const value = unit === 'mi' ? km * KM_TO_MI : km
  return `${value.toFixed(1)} ${unit}`
}

interface SidebarProps {
  stores: Store[]
  drivers: Driver[]
  routes: DriverRoute[]
  selectedDriverIds: string[]
  onToggleDriver: (driverId: string) => void
  onReorderStops: (driverId: string, storeIds: string[]) => void
  onResequenceRoute: (driverId: string, strategy: RouteStrategy) => void
  onEditDrivers: () => void
  onOpenSettings: () => void
  distanceUnit: 'mi' | 'km'
}

export default function Sidebar({
  stores,
  drivers,
  routes,
  selectedDriverIds,
  onToggleDriver,
  onReorderStops,
  onResequenceRoute,
  onEditDrivers,
  onOpenSettings,
  distanceUnit,
}: SidebarProps) {
  // An empty selection means "all drivers" for stat purposes too.
  const visibleRoutes =
    selectedDriverIds.length === 0
      ? routes
      : routes.filter((route) => selectedDriverIds.includes(route.driver.id))

  const totalOrders = stores.length
  const scheduledOrders = visibleRoutes.reduce((sum, route) => sum + route.stops.length, 0)
  const unscheduledOrders = totalOrders - scheduledOrders

  const [collapsed, setCollapsed] = useState(false)
  const [dragState, setDragState] = useState<{ driverId: string; fromIndex: number } | null>(null)
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null)
  // Which sort strategy is showing in each driver's dropdown -- purely
  // client-side display state, since the backend recomputes on demand and
  // doesn't track a "current strategy" per route.
  const [strategyByDriver, setStrategyByDriver] = useState<Record<string, RouteStrategy>>({})

  const handleStopDragStart = (e: React.DragEvent, driverId: string, index: number) => {
    // Firefox (and some Chrome versions) refuse to start a native HTML5 drag
    // at all unless dataTransfer carries data — the payload itself is unused
    // since reordering is driven by React state, not the drop event.
    e.dataTransfer.setData('text/plain', String(index))
    e.dataTransfer.effectAllowed = 'move'
    setDragState({ driverId, fromIndex: index })
  }

  const handleStopDragOver = (e: React.DragEvent, driverId: string, index: number) => {
    if (!dragState || dragState.driverId !== driverId) return
    e.preventDefault()
    setDragOverIndex(index)
  }

  const handleStopDrop = (e: React.DragEvent, driverId: string, index: number, stops: DriverRoute['stops']) => {
    e.preventDefault()
    setDragState(null)
    setDragOverIndex(null)
    if (!dragState || dragState.driverId !== driverId || dragState.fromIndex === index) return

    const storeIds = stops.map((s) => s.store.id)
    const [moved] = storeIds.splice(dragState.fromIndex, 1)
    storeIds.splice(index, 0, moved)
    onReorderStops(driverId, storeIds)
  }

  const handleStopDragEnd = () => {
    setDragState(null)
    setDragOverIndex(null)
  }

  return (
    <aside className={collapsed ? 'sidebar collapsed' : 'sidebar'}>
      {!collapsed && (
      <div className="sidebar-content">
        <div className="sidebar-title-row">
          <h1>OptiRoute</h1>
          <button className="settings-button" onClick={onOpenSettings} aria-label="Settings">
            ⚙
          </button>
        </div>
        <p className="subtitle">Liquor delivery route planning</p>

        <ul className="stats-grid">
          <li>
            <span className="stat-value">{totalOrders}</span>
            <span className="stat-label">Total orders</span>
          </li>
          <li>
            <span className="stat-value">{scheduledOrders}</span>
            <span className="stat-label">Scheduled</span>
          </li>
          <li>
            <span className="stat-value">{unscheduledOrders}</span>
            <span className="stat-label">Unscheduled</span>
          </li>
          <li>
            <span className="stat-value">{visibleRoutes.length}</span>
            <span className="stat-label">Routes created</span>
          </li>
        </ul>

        <div className="drivers-section-header">
          <h2>Drivers</h2>
          <button className="edit-drivers-button" onClick={onEditDrivers}>
            Edit Drivers
          </button>
        </div>
        <ul className="driver-list">
          {drivers.map((driver) => {
            const route = routes.find((r) => r.driver.id === driver.id)
            return (
              <li key={driver.id}>
                <label className="driver-checkbox">
                  <input
                    type="checkbox"
                    checked={selectedDriverIds.includes(driver.id)}
                    onChange={() => onToggleDriver(driver.id)}
                  />
                  <strong>{driver.name}</strong>
                </label>
                {route && (
                  <>
                    <div className="route-stats-row">
                      <span>
                        {route.stops.length} stops · {formatDistance(route.total_distance_km, distanceUnit)}
                      </span>
                      <select
                        className="route-strategy-select"
                        aria-label={`Sort ${driver.name}'s route`}
                        value={strategyByDriver[driver.id] ?? 'fastest'}
                        onChange={(e) => {
                          const strategy = e.target.value as RouteStrategy
                          setStrategyByDriver((prev) => ({ ...prev, [driver.id]: strategy }))
                          onResequenceRoute(driver.id, strategy)
                        }}
                      >
                        <option value="fastest">Fastest route</option>
                        <option value="time_windows">Fit all time windows</option>
                      </select>
                    </div>
                    <div>
                      Est. finish: <strong>{route.estimated_finish_time}</strong>
                      {route.estimate_source === 'straight_line_estimate' && (
                        <span className="estimate-note"> (rough estimate — live routing unreachable)</span>
                      )}
                    </div>
                    <div className="route-time-breakdown">
                      {formatDuration(route.total_drive_minutes)} driving ·{' '}
                      {formatDuration(route.total_service_minutes)} stops
                    </div>
                    <ul className="stop-etas">
                      {route.stops.map((stop, index) => (
                        <li
                          key={stop.store.id}
                          draggable
                          className={
                            dragState?.driverId === driver.id && dragOverIndex === index
                              ? 'stop-drag-over'
                              : undefined
                          }
                          onDragStart={(e) => handleStopDragStart(e, driver.id, index)}
                          onDragOver={(e) => handleStopDragOver(e, driver.id, index)}
                          onDrop={(e) => handleStopDrop(e, driver.id, index, route.stops)}
                          onDragEnd={handleStopDragEnd}
                        >
                          <span className="stop-drag-handle">⠿</span>
                          {stop.sequence}. {stop.store.name} — {stop.eta}
                          {stop.on_time === false && <span className="late-flag"> ⚠ outside time window</span>}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </li>
            )
          })}
        </ul>
      </div>
      )}
      <button
        className="sidebar-collapse-toggle"
        onClick={() => setCollapsed((c) => !c)}
        aria-expanded={!collapsed}
        aria-label={collapsed ? 'Show driver menu' : 'Hide driver menu'}
      >
        {collapsed ? '▸' : '◂'}
      </button>
    </aside>
  )
}
