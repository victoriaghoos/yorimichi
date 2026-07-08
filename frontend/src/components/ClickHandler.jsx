import { useMapEvents } from 'react-leaflet'

function ClickHandler({ onMapClick }) {
  useMapEvents({
    click(event) {
      onMapClick(event.latlng.lat, event.latlng.lng)
    },
  })
  return null
}

export default ClickHandler