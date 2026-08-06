import maplibregl, { Map as MapLibreMap, Marker } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useMemo, useRef } from 'react'
import type { Driver, DriverRoute, Store } from '../types'
import OrdersPanel from './OrdersPanel'

const ROUTE_COLORS = ['#e63946', '#2a9d8f', '#457b9d', '#f4a261', '#9d4edd', '#ffb703']

interface MapProps {
  stores: Store[]
  routes: DriverRoute[]
  drivers: Driver[]
  selectedDriverIds: string[]
  selectedOrderIds: string[]
  onSelectedOrderIdsChange: (updater: string[] | ((prev: string[]) => string[])) => void
  loading: boolean
  onOptimize: (storeIds?: string[]) => void
  onUpdateStore: (storeId: string, patch: Partial<Store>) => void
  onImportOrders: () => void
  center?: [number, number]
}

export default function MapView({
  stores,
  routes,
  drivers,
  selectedDriverIds,
  selectedOrderIds,
  onSelectedOrderIdsChange,
  loading,
  onOptimize,
  onUpdateStore,
  onImportOrders,
  center = [-87.6298, 41.8781],
}: MapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const markersRef = useRef<Marker[]>([])

  // Only the checked drivers' routes are shown; an empty selection shows everyone.
  const visibleRoutes = useMemo(
    () =>
      selectedDriverIds.length === 0
        ? routes
        : routes.filter((route) => selectedDriverIds.includes(route.driver.id)),
    [routes, selectedDriverIds],
  )

  const colorForDriver = (driverId: string) => {
    const index = drivers.findIndex((d) => d.id === driverId)
    return ROUTE_COLORS[(index === -1 ? 0 : index) % ROUTE_COLORS.length]
  }

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    mapRef.current = new maplibregl.Map({
      container: containerRef.current,
      // Free, no-API-key vector tile style built on OpenStreetMap data.
      // Swap for MapTiler/Stadia Maps/a self-hosted style for production traffic.
      style: 'https://tiles.openfreemap.org/styles/liberty',
      center,
      zoom: 11,
    })

    mapRef.current.addControl(new maplibregl.NavigationControl(), 'top-right')

    // The sidebar collapses/expands with a CSS width transition, which resizes
    // this container without firing a window resize event — keep the map in sync.
    const resizeObserver = new ResizeObserver(() => mapRef.current?.resize())
    resizeObserver.observe(containerRef.current)

    return () => {
      resizeObserver.disconnect()
      mapRef.current?.remove()
      mapRef.current = null
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    const addMarkers = () => {
      markersRef.current.forEach((m) => m.remove())
      markersRef.current = []

      const stopInfo = new Map<string, { sequence: number; color: string }>()
      for (const route of visibleRoutes) {
        const color = colorForDriver(route.driver.id)
        for (const stop of route.stops) {
          stopInfo.set(stop.store.id, { sequence: stop.sequence, color })
        }
      }

      // With a driver filter active, hide stores that aren't on a visible route.
      // Before any optimization has run there are no routes to filter by, so
      // don't hide anything — otherwise picking a driver would blank the map.
      const filterActive = selectedDriverIds.length > 0 && routes.length > 0
      const visibleStores = filterActive ? stores.filter((store) => stopInfo.has(store.id)) : stores

      for (const store of visibleStores) {
        const info = stopInfo.get(store.id)
        const el = document.createElement('div')
        el.className = 'store-marker'
        if (info) {
          el.classList.add('store-marker-numbered')
          el.style.backgroundColor = info.color
          el.textContent = String(info.sequence)
        }
        if (selectedOrderIds.includes(store.id)) {
          el.classList.add('selected-marker')
        }
        // Click a dot to add/remove it from the shared order selection —
        // the same selection the orders table's row clicks use.
        el.addEventListener('click', (e) => {
          e.stopPropagation()
          onSelectedOrderIdsChange((prev) =>
            prev.includes(store.id) ? prev.filter((id) => id !== store.id) : [...prev, store.id],
          )
        })
        const marker = new maplibregl.Marker({ element: el })
          .setLngLat([store.coordinates.lng, store.coordinates.lat])
          .setPopup(
            new maplibregl.Popup({ offset: 12 }).setHTML(
              `<strong>${store.name}</strong><br/>${store.address}<br/>${store.case_count} cases`,
            ),
          )
          .addTo(map)
        markersRef.current.push(marker)
      }
    }

    if (map.isStyleLoaded()) addMarkers()
    else map.once('load', addMarkers)
  }, [stores, visibleRoutes, drivers, selectedDriverIds, selectedOrderIds, onSelectedOrderIdsChange])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    // Road-snapped geometry comes from the backend's routing call (OSRM).
    // Falls back to straight lines between stops if that call failed.
    const drawRoutes = () => {
      const style = map.getStyle()
      for (const layer of style?.layers ?? []) {
        if (layer.id.startsWith('route-line-')) map.removeLayer(layer.id)
      }
      for (const sourceId of Object.keys(style?.sources ?? {})) {
        if (sourceId.startsWith('route-source-')) map.removeSource(sourceId)
      }

      visibleRoutes.forEach((route) => {
        const coordinates: [number, number][] =
          route.geometry ?? [
            [route.driver.depot.lng, route.driver.depot.lat],
            ...route.stops.map((s): [number, number] => [
              s.store.coordinates.lng,
              s.store.coordinates.lat,
            ]),
          ]
        const sourceId = `route-source-${route.driver.id}`
        const layerId = `route-line-${route.driver.id}`

        map.addSource(sourceId, {
          type: 'geojson',
          data: {
            type: 'Feature',
            properties: {},
            geometry: { type: 'LineString', coordinates },
          },
        })
        map.addLayer({
          id: layerId,
          type: 'line',
          source: sourceId,
          layout: { 'line-join': 'round', 'line-cap': 'round' },
          paint: {
            'line-color': colorForDriver(route.driver.id),
            'line-width': 4,
            'line-opacity': 0.8,
          },
        })
      })
    }

    if (map.isStyleLoaded()) drawRoutes()
    else map.once('load', drawRoutes)
  }, [visibleRoutes, drivers])

  return (
    <div className="map-wrapper">
      <div ref={containerRef} className="map-container" />
      <OrdersPanel
        stores={stores}
        routes={visibleRoutes}
        loading={loading}
        onImportOrders={onImportOrders}
        onOptimize={onOptimize}
        onUpdateStore={onUpdateStore}
        selectedOrderIds={selectedOrderIds}
        onSelectedOrderIdsChange={onSelectedOrderIdsChange}
      />
    </div>
  )
}
