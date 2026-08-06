import { useEffect, useRef, useState } from 'react'
import type { DriverRoute, Store } from '../types'

interface OrderRow {
  orderId: string
  location: string
  address: string
  timeWindowStart: string
  timeWindowEnd: string
  caseCount: number
  stopNumber: number | null
}

interface OrdersPanelProps {
  stores: Store[]
  routes: DriverRoute[]
  loading: boolean
  onImportOrders: () => void
  onEditOffice: () => void
  onOptimize: (storeIds?: string[]) => void
  onUpdateStore: (storeId: string, patch: Partial<Store>) => void
  selectedOrderIds: string[]
  onSelectedOrderIdsChange: (updater: string[] | ((prev: string[]) => string[])) => void
}

function buildRows(stores: Store[], routes: DriverRoute[]): OrderRow[] {
  // Always driven by the live (editable) store list; stop numbers are
  // overlaid from whichever routes are currently visible.
  const stopNumberByStoreId = new Map<string, number>()
  for (const route of routes) {
    for (const stop of route.stops) {
      stopNumberByStoreId.set(stop.store.id, stop.sequence)
    }
  }

  return stores.map((store) => ({
    orderId: store.id,
    location: store.name,
    address: store.address,
    timeWindowStart: store.time_window_start,
    timeWindowEnd: store.time_window_end,
    caseCount: store.case_count,
    stopNumber: stopNumberByStoreId.get(store.id) ?? null,
  }))
}

export default function OrdersPanel({
  stores,
  routes,
  loading,
  onImportOrders,
  onEditOffice,
  onOptimize,
  onUpdateStore,
  selectedOrderIds,
  onSelectedOrderIdsChange,
}: OrdersPanelProps) {
  const [collapsed, setCollapsed] = useState(false)
  const [editMode, setEditMode] = useState(false)
  const [lastClickedIndex, setLastClickedIndex] = useState<number | null>(null)
  const [optimizeMenuOpen, setOptimizeMenuOpen] = useState(false)
  const optimizeMenuRef = useRef<HTMLDivElement>(null)

  const rows = buildRows(stores, routes)

  useEffect(() => {
    if (!optimizeMenuOpen) return
    const handleClickOutside = (e: MouseEvent) => {
      if (optimizeMenuRef.current && !optimizeMenuRef.current.contains(e.target as Node)) {
        setOptimizeMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [optimizeMenuOpen])

  const handleRowClick = (index: number, orderId: string, event: React.MouseEvent) => {
    if (event.shiftKey && lastClickedIndex !== null) {
      const start = Math.min(lastClickedIndex, index)
      const end = Math.max(lastClickedIndex, index)
      const rangeIds = rows.slice(start, end + 1).map((r) => r.orderId)
      onSelectedOrderIdsChange((prev) => Array.from(new Set([...prev, ...rangeIds])))
    } else {
      onSelectedOrderIdsChange((prev) =>
        prev.includes(orderId) ? prev.filter((id) => id !== orderId) : [...prev, orderId],
      )
      setLastClickedIndex(index)
    }
  }

  const handleOptimizeAll = () => {
    onOptimize()
    setOptimizeMenuOpen(false)
  }

  const handleOptimizeSelected = () => {
    onOptimize(selectedOrderIds)
    setOptimizeMenuOpen(false)
  }

  return (
    <div className="orders-panel">
      <div className="orders-panel-header">
        <h2>Orders</h2>
        <button
          className="collapse-toggle"
          onClick={() => setCollapsed((c) => !c)}
          aria-expanded={!collapsed}
          aria-label={collapsed ? 'Expand orders' : 'Collapse orders'}
        >
          {collapsed ? '▸' : '▾'}
        </button>
      </div>

      <div className="orders-panel-actions">
        <button onClick={onImportOrders}>Import Orders</button>
        <button onClick={onEditOffice}>Office Location</button>
        <div className="optimize-dropdown" ref={optimizeMenuRef}>
          <button onClick={() => setOptimizeMenuOpen((o) => !o)} disabled={loading}>
            {loading ? 'Optimizing…' : 'Optimize Routes'} <span className="dropdown-caret">▾</span>
          </button>
          {optimizeMenuOpen && (
            <div className="optimize-menu">
              <button onClick={handleOptimizeAll}>Optimize All Orders</button>
              <button onClick={handleOptimizeSelected} disabled={selectedOrderIds.length === 0}>
                Optimize Selected Orders{selectedOrderIds.length > 0 && ` (${selectedOrderIds.length})`}
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="orders-panel-actions-secondary">
        <button className="edit-orders-button" onClick={() => setEditMode((e) => !e)}>
          {editMode ? 'Done Editing' : 'Edit Orders'}
        </button>
      </div>

      {!collapsed && (
        <div className="orders-panel-body">
          <table>
            <thead>
              <tr>
                <th>Order ID</th>
                <th>Location</th>
                <th>Address</th>
                <th>Time Window</th>
                <th>Cases</th>
                <th>Stop #</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) =>
                editMode ? (
                  <tr key={row.orderId}>
                    <td>{row.orderId}</td>
                    <td>
                      <input
                        value={row.location}
                        onChange={(e) => onUpdateStore(row.orderId, { name: e.target.value })}
                      />
                    </td>
                    <td>
                      <input
                        value={row.address}
                        onChange={(e) => onUpdateStore(row.orderId, { address: e.target.value })}
                      />
                    </td>
                    <td className="time-window-cell">
                      <input
                        type="time"
                        value={row.timeWindowStart}
                        onChange={(e) => onUpdateStore(row.orderId, { time_window_start: e.target.value })}
                      />
                      <span> – </span>
                      <input
                        type="time"
                        value={row.timeWindowEnd}
                        onChange={(e) => onUpdateStore(row.orderId, { time_window_end: e.target.value })}
                      />
                    </td>
                    <td>
                      <input
                        className="case-count-input"
                        type="number"
                        min={0}
                        value={row.caseCount}
                        onChange={(e) =>
                          onUpdateStore(row.orderId, { case_count: Number(e.target.value) || 0 })
                        }
                      />
                    </td>
                    <td>{row.stopNumber ?? '—'}</td>
                  </tr>
                ) : (
                  <tr
                    key={row.orderId}
                    className={selectedOrderIds.includes(row.orderId) ? 'selected-row' : undefined}
                    onClick={(e) => handleRowClick(index, row.orderId, e)}
                  >
                    <td>{row.orderId}</td>
                    <td>{row.location}</td>
                    <td>{row.address}</td>
                    <td>
                      {row.timeWindowStart} - {row.timeWindowEnd}
                    </td>
                    <td>{row.caseCount}</td>
                    <td>{row.stopNumber ?? '—'}</td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
