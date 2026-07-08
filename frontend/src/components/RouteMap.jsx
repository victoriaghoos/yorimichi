import { useEffect, useState } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet'
import L from 'leaflet'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
})

const HIGASHIYAMA_CENTER = [34.9949, 135.7850]
const DEFAULT_ROUTE_REQUEST = {
  place: 'Higashiyama Ward, Kyoto, Japan',
  orig_lat: 34.9949,
  orig_lon: 135.785,
  dest_lat: 35.0038,
  dest_lon: 135.7788,
}

function RouteMap() {
  const [routeData, setRouteData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function loadRoute() {
      setError(null)
      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
      const query = new URLSearchParams(DEFAULT_ROUTE_REQUEST).toString()

      try {
        const response = await fetch(`${apiBaseUrl}/route?${query}`)
        if (!response.ok) {
          const detail = await response.text()
          throw new Error(`Route API failed (${response.status}): ${detail}`)
        }
        const data = await response.json()
        if (!cancelled) {
          setRouteData(data)
        }
      } catch (fetchError) {
        if (!cancelled) {
          setError(fetchError instanceof Error ? fetchError.message : 'Unknown route fetch error')
        }
      }
    }

    loadRoute()
    return () => {
      cancelled = true
    }
  }, [])

  const baselineCoordinates = routeData?.baseline?.coordinates ?? []
  const scenicCoordinates = routeData?.scenic?.coordinates ?? []

  const mapCenter = scenicCoordinates.length > 0 ? scenicCoordinates[0] : HIGASHIYAMA_CENTER

  return (
    <div style={{ position: 'relative', height: '100vh', width: '100%' }}>
      <MapContainer center={mapCenter} zoom={16} style={{ height: '100%', width: '100%' }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <Marker position={[DEFAULT_ROUTE_REQUEST.orig_lat, DEFAULT_ROUTE_REQUEST.orig_lon]}>
          <Popup>Start</Popup>
        </Marker>
        <Marker position={[DEFAULT_ROUTE_REQUEST.dest_lat, DEFAULT_ROUTE_REQUEST.dest_lon]}>
          <Popup>Destination</Popup>
        </Marker>

        {baselineCoordinates.length > 1 && (
          <Polyline positions={baselineCoordinates} pathOptions={{ color: '#64748b', weight: 5, opacity: 0.85 }} />
        )}
        {scenicCoordinates.length > 1 && (
          <Polyline positions={scenicCoordinates} pathOptions={{ color: '#0f766e', weight: 6, opacity: 0.95 }} />
        )}
      </MapContainer>

      <div
        style={{
          position: 'absolute',
          top: 12,
          left: 12,
          zIndex: 1000,
          background: 'rgba(255, 255, 255, 0.92)',
          borderRadius: 10,
          padding: '10px 12px',
          border: '1px solid #cbd5e1',
          textAlign: 'left',
          fontSize: 13,
          lineHeight: 1.4,
          maxWidth: 360,
        }}
      >
        {error ? (
          <div style={{ color: '#b91c1c' }}>Error loading route: {error}</div>
        ) : routeData ? (
          <div>
            <div>Scenic: {routeData.scenic.length_meters.toFixed(1)} m</div>
            <div>Baseline: {routeData.baseline.length_meters.toFixed(1)} m</div>
          </div>
        ) : (
          <div>Loading route...</div>
        )}
      </div>
    </div>
  )
}

export default RouteMap