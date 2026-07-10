import { useEffect } from 'react'
import { useMap } from 'react-leaflet'
import type { Coordinate } from '../types'

interface MapFlyToProps {
  position: Coordinate | null
  zoom?: number
}

function MapFlyTo({ position, zoom = 16 }: MapFlyToProps) {
  const map = useMap()

  useEffect(() => {
    if (position) {
      map.flyTo([position.lat, position.lon], zoom, { duration: 1.2 })
    }
  }, [position, zoom, map])

  return null
}

export default MapFlyTo