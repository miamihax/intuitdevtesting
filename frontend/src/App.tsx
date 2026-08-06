import { useEffect, useState } from 'react'
import { api } from './api/client'
import ImportOrdersModal from './components/ImportOrdersModal'
import MapView from './components/Map'
import OfficeSettingsModal from './components/OfficeSettingsModal'
import Sidebar from './components/Sidebar'
import type { Driver, DriverRoute, OfficeLocation, Store } from './types'

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
  const [office, setOffice] = useState<OfficeLocation | null>(null)

  useEffect(() => {
    Promise.all([api.getStores(), api.getDrivers(), api.getOffice()])
      .then(([storesData, driversData, officeData]) => {
        setStores(storesData)
        setDrivers(driversData)
        setOffice(officeData)
      })
      .catch((e: Error) => setError(e.message))
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

  const handleOfficeUpdated = (updated: OfficeLocation) => {
    setOffice(updated)
    // Every driver shares the same depot — keep the local list in sync with
    // the backend so the map/route preview reflects the move immediately.
    setDrivers((prev) => prev.map((driver) => ({ ...driver, depot: updated.coordinates })))
  }

  return (
    <div className="app-shell">
      <Sidebar
        stores={stores}
        drivers={drivers}
        routes={routes}
        selectedDriverIds={selectedDriverIds}
        onToggleDriver={handleToggleDriver}
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
        onImportOrders={() => setImportModalOpen(true)}
        onEditOffice={() => setOfficeModalOpen(true)}
      />
      {error && <div className="error-banner">{error}</div>}
      {importModalOpen && (
        <ImportOrdersModal onClose={() => setImportModalOpen(false)} onStoreImported={handleStoreImported} />
      )}
      {officeModalOpen && (
        <OfficeSettingsModal onClose={() => setOfficeModalOpen(false)} onOfficeUpdated={handleOfficeUpdated} />
      )}
    </div>
  )
}
