import { useEffect, useRef, useState } from 'react'
import type { DriverRoute, Settings, Store } from '../types'
import { formatTime } from '../utils/time'

const todayIso = () => new Date().toISOString().slice(0, 10)

const MIN_PANEL_HEIGHT = 160

interface OrderRow {
  orderId: string
  location: string
  address: string
  approximateLocation: boolean
  timeWindowStart: string
  timeWindowEnd: string
  caseCount: number
  stopNumber: number | null
  deliveryDate: string
}

interface OrdersPanelProps {
  stores: Store[]
  routes: DriverRoute[]
  loading: boolean
  onImportOrders: () => void
  onOptimize: (storeIds?: string[]) => void
  onUpdateStore: (storeId: string, patch: Partial<Store>) => void
  onPersistStore: (storeId: string) => void
  onDeleteStore: (storeId: string) => void
  onDeleteAllStores: () => void
  selectedOrderIds: string[]
  onSelectedOrderIdsChange: (updater: string[] | ((prev: string[]) => string[])) => void
  onFocusOrder: (orderId: string) => void
  driverSelected: boolean
  showAllStops: boolean
  onToggleShowAllStops: () => void
  timeFormat: Settings['time_format']
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
    approximateLocation: store.approximate_location,
    timeWindowStart: store.time_window_start,
    timeWindowEnd: store.time_window_end,
    caseCount: store.case_count,
    stopNumber: stopNumberByStoreId.get(store.id) ?? null,
    deliveryDate: store.delivery_date ?? todayIso(),
  }))
}

export default function OrdersPanel({
  stores,
  routes,
  loading,
  onImportOrders,
  onOptimize,
  onUpdateStore,
  onPersistStore,
  onDeleteStore,
  onDeleteAllStores,
  selectedOrderIds,
  onSelectedOrderIdsChange,
  onFocusOrder,
  driverSelected,
  showAllStops,
  onToggleShowAllStops,
  timeFormat,
}: OrdersPanelProps) {
  const [collapsed, setCollapsed] = useState(false)
  const [editMode, setEditMode] = useState(false)
  const [deleteMode, setDeleteMode] = useState(false)
  const [confirmDeleteAllOpen, setConfirmDeleteAllOpen] = useState(false)
  const [lastClickedIndex, setLastClickedIndex] = useState<number | null>(null)
  const [optimizeMenuOpen, setOptimizeMenuOpen] = useState(false)
  const optimizeMenuRef = useRef<HTMLDivElement>(null)
  // Empty string = show every order regardless of delivery date.
  const [dateFilter, setDateFilter] = useState('')
  // null = not resized yet -- CSS's default max-height governs. Set once the
  // user drags the handle at the top of the panel; persists until they drag
  // again (collapsing/expanding via the header toggle doesn't reset it).
  const [panelHeight, setPanelHeight] = useState<number | null>(null)
  const [resizing, setResizing] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)

  const allRows = buildRows(stores, routes)
  const rows = dateFilter ? allRows.filter((row) => row.deliveryDate === dateFilter) : allRows

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
    onFocusOrder(orderId)
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

  const handleExportLog = () => {
    // Store IDs are the invoice number itself whenever one was extracted
    // (see orders.unique_store_id) -- only fall back to the id for orders
    // imported before the invoice_number field existed, and only when that
    // id doesn't look like the random "import-XXXXXXXX" fallback used when
    // no invoice number was found at all.
    const invoiceNumbers = stores
      .map((store) => store.invoice_number ?? (store.id.startsWith('import-') ? null : store.id))
      .filter((n): n is string => Boolean(n))

    const content = invoiceNumbers.length > 0 ? invoiceNumbers.join('\n') + '\n' : ''
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `import-log-${new Date().toISOString().slice(0, 10)}.txt`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  // Dragging up should grow the panel, dragging down should shrink it --
  // the panel is anchored to the bottom of the map (see .orders-panel), so
  // growing it means moving its top edge toward the cursor, i.e. increasing
  // height by however far the cursor moved up from the drag's start.
  const handleResizeStart = (e: React.MouseEvent) => {
    e.preventDefault()
    const panel = panelRef.current
    if (!panel) return
    const startY = e.clientY
    const startHeight = panel.getBoundingClientRect().height
    // Leave a small gap so the handle never reaches all the way to the map's
    // top edge (nav controls, etc. live up there).
    const maxHeight = (panel.parentElement?.getBoundingClientRect().height ?? window.innerHeight) - 24
    setResizing(true)

    const onMouseMove = (ev: MouseEvent) => {
      const next = startHeight + (startY - ev.clientY)
      setPanelHeight(Math.min(maxHeight, Math.max(MIN_PANEL_HEIGHT, next)))
    }
    const onMouseUp = () => {
      setResizing(false)
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
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
    <div
      className="orders-panel"
      ref={panelRef}
      style={!collapsed && panelHeight != null ? { height: panelHeight } : undefined}
    >
      {!collapsed && (
        <div
          className={resizing ? 'orders-panel-resize-handle resizing' : 'orders-panel-resize-handle'}
          onMouseDown={handleResizeStart}
        />
      )}
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
        <label className="orders-date-filter">
          Delivery date
          <input type="date" value={dateFilter} onChange={(e) => setDateFilter(e.target.value)} />
        </label>
        {dateFilter && (
          <button onClick={() => setDateFilter('')}>Show All Dates</button>
        )}
        <button onClick={onImportOrders}>Import Orders</button>
        <button onClick={handleExportLog}>Export Log</button>
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
        <button
          className="edit-orders-button"
          onClick={() => {
            setEditMode((e) => !e)
            setDeleteMode(false)
          }}
        >
          {editMode ? 'Done Editing' : 'Edit Orders'}
        </button>
        <button
          className="delete-orders-button"
          onClick={() => {
            setDeleteMode((d) => !d)
            setEditMode(false)
          }}
        >
          {deleteMode ? 'Done Deleting' : 'Delete Orders'}
        </button>
        {deleteMode && (
          <button className="delete-all-orders-button" onClick={() => setConfirmDeleteAllOpen(true)}>
            Delete All Orders
          </button>
        )}
        {driverSelected && (
          <button className="show-all-stops-button" onClick={onToggleShowAllStops}>
            {showAllStops ? 'Show Driver Stops' : 'Show All Stops'}
          </button>
        )}
      </div>

      {!collapsed && (
        <div className="orders-panel-body">
          <table>
            <thead>
              <tr>
                <th>Order ID</th>
                <th>Location</th>
                <th>Address</th>
                <th>Delivery Date</th>
                <th>Time Window</th>
                <th>Cases</th>
                <th>Stop #</th>
                {deleteMode && <th></th>}
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
                        onBlur={() => onPersistStore(row.orderId)}
                      />
                    </td>
                    <td>
                      <input
                        value={row.address}
                        onChange={(e) => onUpdateStore(row.orderId, { address: e.target.value })}
                        onBlur={() => onPersistStore(row.orderId)}
                      />
                    </td>
                    <td>
                      <input
                        type="date"
                        value={row.deliveryDate}
                        onChange={(e) => onUpdateStore(row.orderId, { delivery_date: e.target.value })}
                        onBlur={() => onPersistStore(row.orderId)}
                      />
                    </td>
                    <td className="time-window-cell">
                      <input
                        type="time"
                        value={row.timeWindowStart}
                        onChange={(e) => onUpdateStore(row.orderId, { time_window_start: e.target.value })}
                        onBlur={() => onPersistStore(row.orderId)}
                      />
                      <span> – </span>
                      <input
                        type="time"
                        value={row.timeWindowEnd}
                        onChange={(e) => onUpdateStore(row.orderId, { time_window_end: e.target.value })}
                        onBlur={() => onPersistStore(row.orderId)}
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
                        onBlur={() => onPersistStore(row.orderId)}
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
                    <td>
                      {row.address}
                      {row.approximateLocation && (
                        <span
                          className="approximate-location-flag"
                          title="Exact address not found — located to the ZIP code area only"
                        >
                          {' '}⚠
                        </span>
                      )}
                    </td>
                    <td>{row.deliveryDate}</td>
                    <td>
                      {formatTime(row.timeWindowStart, timeFormat)} - {formatTime(row.timeWindowEnd, timeFormat)}
                    </td>
                    <td>{row.caseCount}</td>
                    <td>{row.stopNumber ?? '—'}</td>
                    {deleteMode && (
                      <td>
                        <button
                          className="delete-order-button"
                          onClick={(e) => {
                            e.stopPropagation()
                            onDeleteStore(row.orderId)
                          }}
                        >
                          Delete
                        </button>
                      </td>
                    )}
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      )}

      {confirmDeleteAllOpen && (
        <div className="import-modal-overlay" onClick={() => setConfirmDeleteAllOpen(false)}>
          <div className="import-modal" onClick={(e) => e.stopPropagation()}>
            <div className="import-modal-header">
              <h2>Delete All Orders</h2>
              <button
                className="collapse-toggle"
                onClick={() => setConfirmDeleteAllOpen(false)}
                aria-label="Close"
              >
                ✕
              </button>
            </div>
            <p className="import-modal-hint">
              This permanently deletes all {stores.length} order{stores.length === 1 ? '' : 's'}. This can't be
              undone.
            </p>
            <div className="confirm-delete-all-actions">
              <button onClick={() => setConfirmDeleteAllOpen(false)}>Cancel</button>
              <button
                className="delete-all-orders-button"
                onClick={() => {
                  onDeleteAllStores()
                  setConfirmDeleteAllOpen(false)
                  setDeleteMode(false)
                }}
              >
                Delete All
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
