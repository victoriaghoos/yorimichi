import { useEffect, useState, useCallback } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet'
import L, { type PathOptions } from 'leaflet'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'
import ClickHandler from './ClickHandler'
import MapFlyTo from './MapFlyTo'
import './RouteMap.css'
import type { Coordinate, RouteResponse, ScenicCategory, StatusMessage } from '../types'

// @ts-expect-error: Leaflet's default icon setup requires deleting this internal property which isn't part of Leaflet's public TypeScript definitions.
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
})

const HIGASHIYAMA_CENTER: [number, number] = [34.9949, 135.7850]
const MOBILE_BREAKPOINT = 768

const ROUTE_STYLES: Record<'baseline' | 'scenic', PathOptions> = {
  baseline: {
    color: '#2563eb',
    weight: 5,
    opacity: 0.86,
    dashArray: '10 8',
  },
  scenic: {
    color: '#f59e0b',
    weight: 6,
    opacity: 0.94,
  },
}

const SCENIC_CATEGORIES: ScenicCategory[] = [
  { key: 'shrines_temples', emoji: '⛩️', jpLabel: '神社仏閣', sublabel: 'Shrines & Temples' },
  { key: 'parks', emoji: '🌸', jpLabel: '公園・緑地', sublabel: 'Parks & Green Spaces' },
  { key: 'waterside', emoji: '🌊', jpLabel: '水辺', sublabel: 'Waterside' },
  { key: 'historic_sites', emoji: '🏯', jpLabel: '史跡', sublabel: 'Historic Sites' },
  { key: 'nature', emoji: '🌳', jpLabel: '自然', sublabel: 'Nature' },
  { key: 'viewpoints', emoji: '🌉', jpLabel: '景観スポット', sublabel: 'Scenic Viewpoints' },
]

function RouteMap() {
  const [origin, setOrigin] = useState<Coordinate | null>(null)
  const [destination, setDestination] = useState<Coordinate | null>(null)
  const [routeData, setRouteData] = useState<RouteResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [activeCategories, setActiveCategories] = useState<Set<string>>(new Set())
  const [panelExpanded, setPanelExpanded] = useState<boolean>(() => {
    if (typeof window === 'undefined') return true
    return window.innerWidth > MOBILE_BREAKPOINT
  })

  useEffect(() => {
    const media = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`)
    const handleChange = (event: MediaQueryListEvent | MediaQueryList) => {
      setPanelExpanded(!event.matches)
    }

    handleChange(media)
    media.addEventListener('change', handleChange)
    return () => media.removeEventListener('change', handleChange)
  }, [])

  const toggleCategory = useCallback((categoryKey: string) => {
    setActiveCategories((prev) => {
      const next = new Set(prev)
      if (next.has(categoryKey)) {
        next.delete(categoryKey)
      } else {
        next.add(categoryKey)
      }
      return next
    })
  }, [])

  const handleMapClick = useCallback((lat: number, lon: number) => {
    if (!origin || destination) {
      setOrigin({ lat, lon })
      setDestination(null)
      setRouteData(null)
      setError(null)
    } else {
      setDestination({ lat, lon })
    }
  }, [origin, destination])

  const handleUseMyLocation = useCallback(() => {
    if (!navigator.geolocation) {
      setError('Geolocation is not supported by your browser.')
      return
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setOrigin({ lat: position.coords.latitude, lon: position.coords.longitude })
        setDestination(null)
        setRouteData(null)
        setError(null)
      },
      (geoError) => {
        setError(`Could not get your location: ${geoError.message}`)
      },
      { enableHighAccuracy: true, timeout: 10000 }
    )
  }, [])

  const handleReset = useCallback(() => {
    setOrigin(null)
    setDestination(null)
    setRouteData(null)
    setActiveCategories(new Set())
    setError(null)
  }, [])

  useEffect(() => {
    if (!origin || !destination) return

    let cancelled = false

    async function loadRoute() {
      setLoading(true)
      setError(null)
      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
      const params: Record<string, string> = {
        orig_lat: String(origin!.lat),
        orig_lon: String(origin!.lon),
        dest_lat: String(destination!.lat),
        dest_lon: String(destination!.lon),
      }
      if (activeCategories.size > 0) {
        params.boost_categories = Array.from(activeCategories).join(',')
      }
      const query = new URLSearchParams(params).toString()

      try {
        const response = await fetch(`${apiBaseUrl}/route?${query}`)
        if (!response.ok) {
          const detail = await response.text()
          throw new Error(`Route API failed (${response.status}): ${detail}`)
        }
        const data: RouteResponse = await response.json()
        if (!cancelled) {
          setRouteData(data)
        }
      } catch (fetchError) {
        if (!cancelled) {
          setError(fetchError instanceof Error ? fetchError.message : 'Unknown route fetch error')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadRoute()
    return () => {
      cancelled = true
    }
  }, [origin, destination, activeCategories])

  const baselineCoordinates = routeData?.baseline?.coordinates ?? []
  const scenicCoordinates = routeData?.scenic?.coordinates ?? []

  const getStatusMessage = (): StatusMessage => {
    if (error) return { kind: 'error', text: `Error: ${error}` }
    if (loading) return { kind: 'info', text: 'Loading route...' }
    if (routeData) {
      return {
        kind: 'metrics',
        scenic: routeData.scenic.length_meters.toFixed(1),
        baseline: routeData.baseline.length_meters.toFixed(1),
      }
    }
    if (origin && !destination) return { kind: 'info', text: 'Click the map to set your destination.' }
    return { kind: 'info', text: 'Click the map, or use your location, to set a starting point.' }
  }

  const status = getStatusMessage()

  return (
    <div className="route-map-shell">
      <MapContainer center={HIGASHIYAMA_CENTER} zoom={15} style={{ height: '100%', width: '100%' }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <ClickHandler onMapClick={handleMapClick} />
        <MapFlyTo position={origin} />

        {origin && (
          <Marker position={[origin.lat, origin.lon]}>
            <Popup>Start</Popup>
          </Marker>
        )}
        {destination && (
          <Marker position={[destination.lat, destination.lon]}>
            <Popup>Destination</Popup>
          </Marker>
        )}

        {baselineCoordinates.length > 1 && (
          <Polyline positions={baselineCoordinates} pathOptions={ROUTE_STYLES.baseline} />
        )}
        {scenicCoordinates.length > 1 && (
          <Polyline positions={scenicCoordinates} pathOptions={ROUTE_STYLES.scenic} />
        )}
      </MapContainer>

      <div className={`control-panel-wrap ${panelExpanded ? 'expanded' : 'collapsed'}`}>
        <button
          className="panel-toggle"
          onClick={() => setPanelExpanded((prev) => !prev)}
          aria-label={panelExpanded ? 'Collapse panel' : 'Expand panel'}
          title={panelExpanded ? 'Collapse panel' : 'Expand panel'}
        >
          {panelExpanded ? '▾' : '≡'}
        </button>

        {panelExpanded && (
          <div className="control-panel">
            <div className="panel-head">
              <h2>Route Controls</h2>
            </div>

            <div className="status-box">
              {status.kind === 'metrics' ? (
                <div className="status-metrics">
                  <div>
                    <span className="metric-dot scenic" aria-hidden="true" /> Scenic: {status.scenic} m
                  </div>
                  <div>
                    <span className="metric-dot baseline" aria-hidden="true" /> Baseline: {status.baseline} m
                  </div>
                </div>
              ) : (
                <div className={status.kind === 'error' ? 'status-error' : 'status-info'}>{status.text}</div>
              )}
            </div>

            <div className="route-legend" aria-label="Route legend">
              <span>
                <span className="legend-line baseline" aria-hidden="true" />
                <span className="legend-dot baseline" aria-hidden="true" /> Baseline
              </span>
              <span>
                <span className="legend-line scenic" aria-hidden="true" />
                <span className="legend-dot scenic" aria-hidden="true" /> Scenic
              </span>
            </div>

            <div className="action-row">
              <button onClick={handleUseMyLocation} className="map-action-btn">
                Use my location
              </button>
              {(origin || destination) && (
                <button onClick={handleReset} className="map-action-btn secondary">
                  Reset
                </button>
              )}
            </div>

            <div className="category-grid" role="group" aria-label="Scenic preference boosts">
              {SCENIC_CATEGORIES.map((category) => {
                const isActive = activeCategories.has(category.key)
                return (
                  <button
                    key={category.key}
                    onClick={() => toggleCategory(category.key)}
                    className={`category-card ${isActive ? 'active' : ''}`}
                    aria-pressed={isActive}
                  >
                    <div className="category-emoji-row">
                      <span className="category-emoji" aria-hidden="true">{category.emoji}</span>
                      {isActive && <span className="active-check" aria-hidden="true">✓</span>}
                    </div>
                    <div className="category-jp">{category.jpLabel}</div>
                    <div className="category-sub">{category.sublabel}</div>
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default RouteMap