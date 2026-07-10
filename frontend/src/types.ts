export interface Coordinate {
  lat: number
  lon: number
}

export interface RouteDTO {
  node_ids: string[]
  length_meters: number
  coordinates: [number, number][]
}

export interface RouteResponse {
  baseline: RouteDTO
  scenic: RouteDTO
}

export interface ScenicCategory {
  key: string
  emoji: string
  jpLabel: string
  sublabel: string
}

export type StatusMessage =
  | { kind: 'error'; text: string }
  | { kind: 'info'; text: string }
  | { kind: 'metrics'; scenic: string; baseline: string }