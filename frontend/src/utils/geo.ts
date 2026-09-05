const EARTH_RADIUS_METERS = 6371000

export function haversineMeters(a: [number, number], b: [number, number]): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180
  const dLat = toRad(b[0] - a[0])
  const dLon = toRad(b[1] - a[1])
  const lat1 = toRad(a[0])
  const lat2 = toRad(b[0])
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2
  return 2 * EARTH_RADIUS_METERS * Math.asin(Math.sqrt(h))
}

export interface RouteProgress {
  nearestIndex: number
  distanceToRouteMeters: number
  remainingMeters: number
}

/**
 * Finds the route vertex nearest to the walker's current position and sums the
 * remaining path length from there to the end of the route.
 */
export function trackProgressAlongRoute(
  coordinates: [number, number][],
  currentPosition: [number, number]
): RouteProgress | null {
  if (coordinates.length < 2) return null

  let nearestIndex = 0
  let distanceToRouteMeters = Infinity
  for (let i = 0; i < coordinates.length; i++) {
    const d = haversineMeters(coordinates[i], currentPosition)
    if (d < distanceToRouteMeters) {
      distanceToRouteMeters = d
      nearestIndex = i
    }
  }

  let remainingMeters = 0
  for (let i = nearestIndex; i < coordinates.length - 1; i++) {
    remainingMeters += haversineMeters(coordinates[i], coordinates[i + 1])
  }

  return { nearestIndex, distanceToRouteMeters, remainingMeters }
}
