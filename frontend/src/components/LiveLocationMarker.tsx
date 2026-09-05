import { Circle, CircleMarker } from 'react-leaflet'
import type { Coordinate } from '../types'

interface LiveLocationMarkerProps {
  position: Coordinate
  accuracyMeters?: number
}

function LiveLocationMarker({ position, accuracyMeters }: LiveLocationMarkerProps) {
  const center: [number, number] = [position.lat, position.lon]

  return (
    <>
      {accuracyMeters && accuracyMeters > 0 && (
        <Circle
          center={center}
          radius={accuracyMeters}
          pathOptions={{ color: '#2563eb', weight: 1, opacity: 0.25, fillColor: '#2563eb', fillOpacity: 0.12 }}
        />
      )}
      <CircleMarker
        center={center}
        radius={9}
        pathOptions={{ color: '#ffffff', weight: 3, fillColor: '#2563eb', fillOpacity: 1 }}
        className="live-location-dot"
      />
    </>
  )
}

export default LiveLocationMarker
