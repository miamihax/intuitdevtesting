import { useState } from 'react'
import type { Driver, DriverRoute, Store } from '../types'

interface SidebarProps {
  stores: Store[]
  drivers: Driver[]
  routes: DriverRoute[]
  selectedDriverIds: string[]
  onToggleDriver: (driverId: string) => void
  onEditDrivers: () => void
}

export default function Sidebar({
  stores,
  drivers,
  routes,
  selectedDriverIds,
  onToggleDriver,
  onEditDrivers,
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

  return (
    <aside className={collapsed ? 'sidebar collapsed' : 'sidebar'}>
      {!collapsed && (
      <div className="sidebar-content">
        <h1>OptiRoute</h1>
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
                      {route.total_drive_minutes} min driving · {route.total_service_minutes} min stops
                    </div>
                    <ul className="stop-etas">
                      {route.stops.map((stop) => (
                        <li key={stop.store.id}>
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
