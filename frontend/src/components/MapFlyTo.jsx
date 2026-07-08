import { useEffect } from 'react'
import { useMap } from 'react-leaflet'

function MapFlyTo({ position, zoom = 16 }) {
  const map = useMap()

  useEffect(() => {
    if (position) {
      map.flyTo([position.lat, position.lon], zoom, { duration: 1.2 })
    }
  }, [position, zoom, map])

  return null
}

export default MapFlyTo