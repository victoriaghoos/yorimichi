import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'
import type { Coordinate } from '../types'

interface FollowPositionProps {
  position: Coordinate | null
  enabled: boolean
}

function FollowPosition({ position, enabled }: FollowPositionProps) {
  const map = useMap()
  const hasCenteredOnce = useRef(false)

  useEffect(() => {
    if (!position || !enabled) return
    const target: [number, number] = [position.lat, position.lon]
    if (!hasCenteredOnce.current) {
      map.setView(target, Math.max(map.getZoom(), 17), { animate: true })
      hasCenteredOnce.current = true
    } else {
      map.panTo(target, { animate: true, duration: 0.5 })
    }
  }, [position, enabled, map])

  useEffect(() => {
    if (!enabled) hasCenteredOnce.current = false
  }, [enabled])

  return null
}

export default FollowPosition
