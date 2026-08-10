import { useState } from 'react'
import type { Driver, DriverRoute, Store } from '../types'

// Converts a decimal minute value (e.g. 45.3) into "1h 45m 18s" instead of
// showing the raw fraction — omits the hours part when there aren't any.
function formatDuration(totalMinutes: number): string {
  const totalSeconds = Math.round(totalMinutes * 60)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  return hours > 0 ? `${hours}h ${minutes}m ${seconds}s` : `${minutes}m ${seconds}s`
}

interface SidebarProps {
  stores: Store[]
  drivers: Driver[]
  routes: DriverRoute[]
  selectedDriverIds: string[]
  onToggleDriver: (driverId: string) => void
  onReorderStops: (driverId: string, storeIds: string[]) => void
  onEditDrivers: () => void
  onOpenSettings: () => void
}

export default function Sidebar({
  stores,
  drivers,
  routes,
  selectedDriverIds,
  onToggleDriver,
  onReorderStops,
  onEditDrivers,
  onOpenSettings,
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

  const handleStopDragStart = (driverId: string, index: number) => {
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
                    <div>
                      {route.stops.length} stops · {route.total_distance_km} km
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
                          onDragStart={() => handleStopDragStart(driver.id, index)}
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
