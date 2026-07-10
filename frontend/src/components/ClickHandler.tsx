import { useMapEvents } from 'react-leaflet'

interface ClickHandlerProps {
  onMapClick: (lat: number, lon: number) => void
}

function ClickHandler({ onMapClick }: ClickHandlerProps) {
  useMapEvents({
    click(event) {
      onMapClick(event.latlng.lat, event.latlng.lng)
    },
  })
  return null
}

export default ClickHandler