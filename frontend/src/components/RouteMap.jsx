import { useEffect, useState, useCallback } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet'
import L from 'leaflet'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'
import ClickHandler from './ClickHandler'
import MapFlyTo from './MapFlyTo'

delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
})

const HIGASHIYAMA_CENTER = [34.9949, 135.7850]
const PLACE = 'Higashiyama Ward, Kyoto, Japan'

function RouteMap() {
  const [origin, setOrigin] = useState(null)
  const [destination, setDestination] = useState(null)
  const [routeData, setRouteData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleMapClick = useCallback((lat, lon) => {
    if (!origin) {
      setOrigin({ lat, lon })
      setDestination(null)
      setRouteData(null)
      setError(null)
    } else if (!destination) {
      setDestination({ lat, lon })
    } else {
      setOrigin({ lat, lon })
      setDestination(null)
      setRouteData(null)
      setError(null)
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
    setError(null)
  }, [])

  useEffect(() => {
    if (!origin || !destination) return

    let cancelled = false

    async function loadRoute() {
      setLoading(true)
      setError(null)
      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
      const query = new URLSearchParams({
        place: PLACE,
        orig_lat: origin.lat,
        orig_lon: origin.lon,
        dest_lat: destination.lat,
        dest_lon: destination.lon,
      }).toString()

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
  }, [origin, destination])

  const baselineCoordinates = routeData?.baseline?.coordinates ?? []
  const scenicCoordinates = routeData?.scenic?.coordinates ?? []

  const getStatusMessage = () => {
    if (error) return { text: `Error: ${error}`, color: '#b91c1c' }
    if (loading) return { text: 'Loading route...', color: '#334155' }
    if (routeData) {
      return {
        text: `Scenic: ${routeData.scenic.length_meters.toFixed(1)} m — Baseline: ${routeData.baseline.length_meters.toFixed(1)} m`,
        color: '#334155',
      }
    }
    if (origin && !destination) return { text: 'Click the map to set your destination.', color: '#334155' }
    return { text: 'Click the map, or use your location, to set a starting point.', color: '#334155' }
  }

  const status = getStatusMessage()

  return (
    <div style={{ position: 'relative', height: '100vh', width: '100%' }}>
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
        <div style={{ color: status.color }}>{status.text}</div>
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <button onClick={handleUseMyLocation} style={{ fontSize: 12, padding: '4px 8px', cursor: 'pointer' }}>
            Use my location
          </button>
          {(origin || destination) && (
            <button onClick={handleReset} style={{ fontSize: 12, padding: '4px 8px', cursor: 'pointer' }}>
              Reset
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default RouteMap