import { useEffect, useState } from 'react'
import { api } from './api/client'
import EditDriversModal from './components/EditDriversModal'
import ImportOrdersModal from './components/ImportOrdersModal'
import MapView from './components/Map'
import OfficeSettingsModal from './components/OfficeSettingsModal'
import SettingsModal from './components/SettingsModal'
import Sidebar from './components/Sidebar'
import type {
  Driver,
  DriverRoute,
  OfficeLocation,
  RouteStop,
  RouteStrategy,
  Settings,
  Store,
  UpdateDriverFields,
} from './types'

const DEFAULT_SETTINGS: Settings = { auto_add_imports: false, distance_unit: 'mi' }

export default function App() {
  const [stores, setStores] = useState<Store[]>([])
  const [drivers, setDrivers] = useState<Driver[]>([])
  const [routes, setRoutes] = useState<DriverRoute[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedDriverIds, setSelectedDriverIds] = useState<string[]>([])
  // Shared between the map (clicking dots) and the orders table (clicking rows).
  const [selectedOrderIds, setSelectedOrderIds] = useState<string[]>([])
  const [importModalOpen, setImportModalOpen] = useState(false)
  const [officeModalOpen, setOfficeModalOpen] = useState(false)
  const [driversModalOpen, setDriversModalOpen] = useState(false)
  const [settingsModalOpen, setSettingsModalOpen] = useState(false)
  const [office, setOffice] = useState<OfficeLocation | null>(null)
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS)

  useEffect(() => {
    Promise.all([api.getStores(), api.getDrivers(), api.getOffice(), api.getSettings()])
      .then(([storesData, driversData, officeData, settingsData]) => {
        setStores(storesData)
        setDrivers(driversData)
        setOffice(officeData)
        setSettings(settingsData)
      })
      .catch((e: Error) => setError(e.message))
  }, [])

  // Orders can appear server-side without any click here (auto-add on
  // import — see Settings). Poll for ones we don't know about yet, merging
  // by ID only so it never clobbers a store already loaded locally.
  useEffect(() => {
    const interval = setInterval(() => {
      api
        .getStores()
        .then((serverStores) => {
          setStores((prev) => {
            const knownIds = new Set(prev.map((s) => s.id))
            const newOnes = serverStores.filter((s) => !knownIds.has(s.id))
            return newOnes.length > 0 ? [...prev, ...newOnes] : prev
          })
        })
        .catch(() => {})
    }, 4000)
    return () => clearInterval(interval)
  }, [])

  const handleOptimize = (storeIds?: string[]) => {
    setLoading(true)
    setError(null)
    // An empty driver selection means "all drivers", matching how the
    // checkboxes already behave for filtering the map/sidebar display.
    const driverIds = selectedDriverIds.length > 0 ? selectedDriverIds : undefined
    api
      .optimize(storeIds, driverIds)
      .then((result) => {
        setRoutes((prev) => {
          if (!driverIds) return result.routes
          // Scoped to specific drivers: keep everyone else's existing route
          // and only replace the ones that were just recomputed.
          const untouched = prev.filter((r) => !driverIds.includes(r.driver.id))
          return [...untouched, ...result.routes]
        })
        setSelectedOrderIds([])
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  // Drag-and-drop reorder in the sidebar (see Sidebar.tsx) hands back the
  // dragged driver's full new stop order. Reorder optimistically so the
  // list responds immediately — ETAs/drive times stay stale until the
  // recomputed route (real distances for the new order) comes back.
  const handleReorderStops = (driverId: string, storeIds: string[]) => {
    const previousRoute = routes.find((r) => r.driver.id === driverId)
    if (!previousRoute) return

    const storeById = new Map(previousRoute.stops.map((s) => [s.store.id, s.store]))
    const stopById = new Map(previousRoute.stops.map((s) => [s.store.id, s]))
    setRoutes((prev) =>
      prev.map((route) =>
        route.driver.id === driverId
          ? {
              ...route,
              stops: storeIds.map(
                (id, i): RouteStop => ({ ...(stopById.get(id) as RouteStop), store: storeById.get(id)!, sequence: i + 1 }),
              ),
            }
          : route,
      ),
    )

    api
      .reorderRoute(driverId, storeIds)
      .then((updatedRoute) => {
        setRoutes((prev) => prev.map((route) => (route.driver.id === driverId ? updatedRoute : route)))
      })
      .catch((e: Error) => {
        setError(e.message)
        setRoutes((prev) => prev.map((route) => (route.driver.id === driverId ? previousRoute : route)))
      })
  }

  // Re-orders one driver's existing stops according to the chosen strategy
  // (see Sidebar's per-route dropdown) rather than a user drag — the backend
  // picks the order, we just hand it the current stop set.
  const handleResequenceRoute = (driverId: string, strategy: RouteStrategy) => {
    const route = routes.find((r) => r.driver.id === driverId)
    if (!route) return
    const storeIds = route.stops.map((s) => s.store.id)

    setLoading(true)
    setError(null)
    api
      .resequenceRoute(driverId, storeIds, strategy)
      .then((updatedRoute) => {
        setRoutes((prev) => prev.map((r) => (r.driver.id === driverId ? updatedRoute : r)))
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  const handleToggleDriver = (driverId: string) => {
    setSelectedDriverIds((prev) =>
      prev.includes(driverId) ? prev.filter((id) => id !== driverId) : [...prev, driverId],
    )
  }

  const handleUpdateStore = (storeId: string, patch: Partial<Store>) => {
    setStores((prev) => prev.map((store) => (store.id === storeId ? { ...store, ...patch } : store)))
  }

  const handleStoreImported = (store: Store) => {
    setStores((prev) => [...prev, store])
  }

  const handleDeleteStore = (storeId: string) => {
    api
      .deleteStore(storeId)
      .then(() => {
        setStores((prev) => prev.filter((store) => store.id !== storeId))
        setSelectedOrderIds((prev) => prev.filter((id) => id !== storeId))
      })
      .catch((e: Error) => setError(e.message))
  }

  const handleOfficeUpdated = (updated: OfficeLocation) => {
    setOffice(updated)
    // Every driver shares the same depot — keep the local list in sync with
    // the backend so the map/route preview reflects the move immediately.
    setDrivers((prev) => prev.map((driver) => ({ ...driver, depot: updated.coordinates })))
  }

  const handleUpdateDriverField = (driverId: string, patch: Partial<Driver>) => {
    setDrivers((prev) => prev.map((driver) => (driver.id === driverId ? { ...driver, ...patch } : driver)))
  }

  // Persists whatever's currently in local state for this driver — called on
  // blur rather than on every keystroke, so editing a name doesn't fire a
  // request per character.
  const handlePersistDriver = (driver: Driver) => {
    const fields: UpdateDriverFields = {
      name: driver.name,
      vehicle_capacity_cases: driver.vehicle_capacity_cases,
      shift_start: driver.shift_start,
      shift_end: driver.shift_end,
    }
    api.updateDriver(driver.id, fields).catch((e: Error) => setError(e.message))
  }

  const handleDriverCreated = (driver: Driver) => {
    setDrivers((prev) => [...prev, driver])
  }

  const handleSettingsChange = (next: Settings) => {
    const previous = settings
    setSettings(next)
    api.updateSettings(next).catch((e: Error) => {
      setError(e.message)
      setSettings(previous)
    })
  }

  const handleDeleteDriver = (driverId: string) => {
    api
      .deleteDriver(driverId)
      .then(() => {
        setDrivers((prev) => prev.filter((driver) => driver.id !== driverId))
        setSelectedDriverIds((prev) => prev.filter((id) => id !== driverId))
      })
      .catch((e: Error) => setError(e.message))
  }

  return (
    <div className="app-shell">
      <Sidebar
        stores={stores}
        drivers={drivers}
        routes={routes}
        selectedDriverIds={selectedDriverIds}
        onToggleDriver={handleToggleDriver}
        onReorderStops={handleReorderStops}
        onResequenceRoute={handleResequenceRoute}
        onEditDrivers={() => setDriversModalOpen(true)}
        onOpenSettings={() => setSettingsModalOpen(true)}
        distanceUnit={settings.distance_unit}
      />
      <MapView
        stores={stores}
        routes={routes}
        drivers={drivers}
        office={office}
        selectedDriverIds={selectedDriverIds}
        selectedOrderIds={selectedOrderIds}
        onSelectedOrderIdsChange={setSelectedOrderIds}
        loading={loading}
        onOptimize={handleOptimize}
        onUpdateStore={handleUpdateStore}
        onDeleteStore={handleDeleteStore}
        onImportOrders={() => setImportModalOpen(true)}
      />
      {error && <div className="error-banner">{error}</div>}
      {importModalOpen && (
        <ImportOrdersModal onClose={() => setImportModalOpen(false)} onStoreImported={handleStoreImported} />
      )}
      {officeModalOpen && (
        <OfficeSettingsModal onClose={() => setOfficeModalOpen(false)} onOfficeUpdated={handleOfficeUpdated} />
      )}
      {settingsModalOpen && (
        <SettingsModal
          settings={settings}
          onSettingsChange={handleSettingsChange}
          onClose={() => setSettingsModalOpen(false)}
          onEditOffice={() => {
            setSettingsModalOpen(false)
            setOfficeModalOpen(true)
          }}
        />
      )}
      {driversModalOpen && (
        <EditDriversModal
          drivers={drivers}
          onClose={() => setDriversModalOpen(false)}
          onDriverCreated={handleDriverCreated}
          onUpdateDriverField={handleUpdateDriverField}
          onPersistDriver={handlePersistDriver}
          onDeleteDriver={handleDeleteDriver}
        />
      )}
    </div>
  )
}
