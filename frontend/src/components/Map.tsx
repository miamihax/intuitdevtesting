import maplibregl, { Map as MapLibreMap, Marker, Popup } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { Driver, DriverRoute, OfficeLocation, RouteStop, Settings, Store } from '../types'
import OrdersPanel from './OrdersPanel'
import { formatTime } from '../utils/time'

// Reads like colored conduit runs on a dispatch schematic rather than a
// pastel chart palette -- saturated/bright so numbered stop markers stay
// legible against the basemap at a glance.
const ROUTE_COLORS = ['#ff7a1a', '#ffd400', '#22e07a', '#29b6ff', '#ff3b3b', '#ffe6a3']

// Store/address text can come from OCR'd imports or QuickBooks data, so it's
// not safe to interpolate directly into Popup#setHTML -- escape it first.
function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function buildStopPopupHtml(
  store: Store,
  timeFormat: Settings['time_format'],
  stop?: RouteStop,
  driverName?: string,
): string {
  const heading = stop ? `Stop ${stop.sequence} — ${escapeHtml(store.name)}` : escapeHtml(store.name)
  const scheduled = stop?.eta ? formatTime(stop.eta, timeFormat) : '—'
  const lines = [
    `<strong>${heading}</strong>`,
    escapeHtml(store.address),
    `Time window: ${formatTime(store.time_window_start, timeFormat)}–${formatTime(store.time_window_end, timeFormat)}`,
    stop ? `Scheduled: ${scheduled}${driverName ? ` (${escapeHtml(driverName)})` : ''}` : 'Not yet scheduled',
  ]
  return lines.join('<br/>')
}

interface MapProps {
  stores: Store[]
  routes: DriverRoute[]
  drivers: Driver[]
  office: OfficeLocation | null
  selectedDriverIds: string[]
  selectedOrderIds: string[]
  onSelectedOrderIdsChange: (updater: string[] | ((prev: string[]) => string[])) => void
  loading: boolean
  onOptimize: (storeIds?: string[]) => void
  onUpdateStore: (storeId: string, patch: Partial<Store>) => void
  onPersistStore: (storeId: string) => void
  onDeleteStore: (storeId: string) => void
  onDeleteAllStores: () => void
  onImportOrders: () => void
  timeFormat: Settings['time_format']
}

export default function MapView({
  stores,
  routes,
  drivers,
  office,
  selectedDriverIds,
  selectedOrderIds,
  onSelectedOrderIdsChange,
  loading,
  onOptimize,
  onUpdateStore,
  onPersistStore,
  onDeleteStore,
  onDeleteAllStores,
  onImportOrders,
  timeFormat,
}: MapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const markersRef = useRef<Marker[]>([])
  const stopPopupsRef = useRef<Popup[]>([])
  const officeMarkerRef = useRef<Marker | null>(null)
  const initializedRef = useRef(false)
  const resizeObserverRef = useRef<ResizeObserver | null>(null)
  const selectionBoxRef = useRef<HTMLDivElement>(null)
  // Overrides the driver-stop filter below to show every stop instead --
  // toggled from the Orders panel's "Show All Stops" button. Reset whenever
  // the driver selection changes so it doesn't silently carry over to a
  // different driver.
  const [showAllStops, setShowAllStops] = useState(false)
  useEffect(() => {
    setShowAllStops(false)
  }, [selectedDriverIds])

  // Only the checked drivers' routes are shown; an empty selection shows everyone.
  const visibleRoutes = useMemo(
    () =>
      selectedDriverIds.length === 0
        ? routes
        : routes.filter((route) => selectedDriverIds.includes(route.driver.id)),
    [routes, selectedDriverIds],
  )

  // With a driver filter active, hide stores that aren't on a visible route.
  // Before any optimization has run there are no routes to filter by, so
  // don't hide anything — otherwise picking a driver would blank the map.
  // "Show All Stops" (Orders panel) overrides this to show everything.
  const visibleStores = useMemo(() => {
    const filterActive = selectedDriverIds.length > 0 && routes.length > 0 && !showAllStops
    if (!filterActive) return stores
    const visibleStoreIds = new Set(visibleRoutes.flatMap((route) => route.stops.map((s) => s.store.id)))
    return stores.filter((store) => visibleStoreIds.has(store.id))
  }, [stores, visibleRoutes, selectedDriverIds, routes, showAllStops])

  const colorForDriver = (driverId: string) => {
    const index = drivers.findIndex((d) => d.id === driverId)
    return ROUTE_COLORS[(index === -1 ? 0 : index) % ROUTE_COLORS.length]
  }

  // Clicking an order (in the table or as a marker) flies the map to its
  // location instead of just toggling selection in place.
  const focusOrder = (orderId: string) => {
    const map = mapRef.current
    const store = stores.find((s) => s.id === orderId)
    if (!map || !store) return
    map.flyTo({ center: [store.coordinates.lng, store.coordinates.lat], zoom: 15, essential: true })
  }

  // Waits for the office location to load before creating the map, so it
  // opens centered there instead of a hardcoded fallback point — then never
  // re-centers on later office edits (initializedRef makes this run once).
  useEffect(() => {
    if (!containerRef.current || initializedRef.current || !office) return
    initializedRef.current = true

    mapRef.current = new maplibregl.Map({
      container: containerRef.current,
      // Free, no-API-key vector tile style built on OpenStreetMap data.
      // Swap for MapTiler/Stadia Maps/a self-hosted style for production traffic.
      style: 'https://tiles.openfreemap.org/styles/liberty',
      center: [office.coordinates.lng, office.coordinates.lat],
      zoom: 11,
    })

    mapRef.current.addControl(new maplibregl.NavigationControl(), 'top-right')

    // The sidebar collapses/expands with a CSS width transition, which resizes
    // this container without firing a window resize event — keep the map in sync.
    const resizeObserver = new ResizeObserver(() => mapRef.current?.resize())
    resizeObserver.observe(containerRef.current)
    resizeObserverRef.current = resizeObserver
  }, [office])

  // Separate from the effect above so this only runs on actual unmount, not
  // on every office update (which would otherwise destroy and recreate the
  // whole map each time the office address changes).
  useEffect(() => {
    return () => {
      resizeObserverRef.current?.disconnect()
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
      stopPopupsRef.current.forEach((p) => p.remove())
      stopPopupsRef.current = []

      const stopByStoreId = new Map<string, { stop: RouteStop; color: string; driverName: string }>()
      for (const route of visibleRoutes) {
        const color = colorForDriver(route.driver.id)
        for (const stop of route.stops) {
          stopByStoreId.set(stop.store.id, { stop, color, driverName: route.driver.name })
        }
      }

      for (const store of visibleStores) {
        const info = stopByStoreId.get(store.id)
        const el = document.createElement('div')
        el.className = 'store-marker'
        if (info) {
          el.classList.add('store-marker-numbered')
          el.style.backgroundColor = info.color
          el.textContent = String(info.stop.sequence)
        }
        if (selectedOrderIds.includes(store.id)) {
          el.classList.add('selected-marker')
        }
        // Click a dot to add/remove it from the shared order selection —
        // the same selection the orders table's row clicks use.
        el.addEventListener('click', (e) => {
          e.stopPropagation()
          focusOrder(store.id)
          onSelectedOrderIdsChange((prev) =>
            prev.includes(store.id) ? prev.filter((id) => id !== store.id) : [...prev, store.id],
          )
        })

        // Hover shows stop number, name, address, time window, and
        // scheduled arrival (if the stop's on a computed route yet).
        const popup = new maplibregl.Popup({ offset: 12, closeButton: false, closeOnClick: false }).setHTML(
          buildStopPopupHtml(store, timeFormat, info?.stop, info?.driverName),
        )
        stopPopupsRef.current.push(popup)
        el.addEventListener('mouseenter', () => {
          popup.setLngLat([store.coordinates.lng, store.coordinates.lat]).addTo(map)
        })
        el.addEventListener('mouseleave', () => popup.remove())

        const marker = new maplibregl.Marker({ element: el })
          .setLngLat([store.coordinates.lng, store.coordinates.lat])
          .addTo(map)
        markersRef.current.push(marker)
      }
    }

    if (map.isStyleLoaded()) addMarkers()
    else map.once('load', addMarkers)
  }, [visibleStores, visibleRoutes, drivers, selectedOrderIds, onSelectedOrderIdsChange, timeFormat])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    const addOfficeMarker = () => {
      officeMarkerRef.current?.remove()
      officeMarkerRef.current = null
      if (!office) return

      const el = document.createElement('div')
      el.className = 'office-marker'
      officeMarkerRef.current = new maplibregl.Marker({ element: el })
        .setLngLat([office.coordinates.lng, office.coordinates.lat])
        .setPopup(
          new maplibregl.Popup({ offset: 12 }).setHTML(
            `<strong>Office</strong>${office.address ? `<br/>${office.address}` : ''}`,
          ),
        )
        .addTo(map)
    }

    if (map.isStyleLoaded()) addOfficeMarker()
    else map.once('load', addOfficeMarker)
  }, [office])

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

  // Alt+drag draws a rectangle over the map; releasing it adds every
  // visible store whose marker falls inside to the shared order selection.
  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    const canvasContainer = map.getCanvasContainer()
    let start: { x: number; y: number } | null = null

    const pointFromEvent = (e: MouseEvent) => {
      const rect = canvasContainer.getBoundingClientRect()
      return { x: e.clientX - rect.left, y: e.clientY - rect.top }
    }

    const renderBox = (a: { x: number; y: number }, b: { x: number; y: number }) => {
      const el = selectionBoxRef.current
      if (!el) return
      el.style.left = `${Math.min(a.x, b.x)}px`
      el.style.top = `${Math.min(a.y, b.y)}px`
      el.style.width = `${Math.abs(a.x - b.x)}px`
      el.style.height = `${Math.abs(a.y - b.y)}px`
      el.style.display = 'block'
    }

    const onMouseMove = (e: MouseEvent) => {
      if (!start) return
      renderBox(start, pointFromEvent(e))
    }

    const onMouseUp = (e: MouseEvent) => {
      if (!start) return
      const end = pointFromEvent(e)
      const minX = Math.min(start.x, end.x)
      const maxX = Math.max(start.x, end.x)
      const minY = Math.min(start.y, end.y)
      const maxY = Math.max(start.y, end.y)
      start = null

      if (selectionBoxRef.current) selectionBoxRef.current.style.display = 'none'
      map.dragPan.enable()
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)

      // A near-zero drag is an accidental nudge, not a deliberate box — ignore it.
      if (maxX - minX < 4 && maxY - minY < 4) return

      const enclosedIds = visibleStores
        .filter((store) => {
          const p = map.project([store.coordinates.lng, store.coordinates.lat])
          return p.x >= minX && p.x <= maxX && p.y >= minY && p.y <= maxY
        })
        .map((store) => store.id)

      if (enclosedIds.length > 0) {
        onSelectedOrderIdsChange((prev) => Array.from(new Set([...prev, ...enclosedIds])))
      }
    }

    const onMouseDown = (e: MouseEvent) => {
      if (!e.altKey || e.button !== 0) return
      e.preventDefault()
      start = pointFromEvent(e)
      // Suspend panning for the duration of the drag so it draws a
      // selection box instead of moving the map.
      map.dragPan.disable()
      renderBox(start, start)
      window.addEventListener('mousemove', onMouseMove)
      window.addEventListener('mouseup', onMouseUp)
    }

    canvasContainer.addEventListener('mousedown', onMouseDown)
    return () => {
      canvasContainer.removeEventListener('mousedown', onMouseDown)
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
      map.dragPan.enable()
    }
  }, [visibleStores, onSelectedOrderIdsChange])

  return (
    <div className="map-wrapper">
      <div ref={containerRef} className="map-container" />
      <div ref={selectionBoxRef} className="map-selection-box" />
      <OrdersPanel
        stores={visibleStores}
        routes={visibleRoutes}
        loading={loading}
        onImportOrders={onImportOrders}
        onOptimize={onOptimize}
        onUpdateStore={onUpdateStore}
        onPersistStore={onPersistStore}
        onDeleteStore={onDeleteStore}
        onDeleteAllStores={onDeleteAllStores}
        selectedOrderIds={selectedOrderIds}
        onSelectedOrderIdsChange={onSelectedOrderIdsChange}
        onFocusOrder={focusOrder}
        driverSelected={selectedDriverIds.length > 0}
        showAllStops={showAllStops}
        onToggleShowAllStops={() => setShowAllStops((v) => !v)}
        timeFormat={timeFormat}
      />
    </div>
  )
}
