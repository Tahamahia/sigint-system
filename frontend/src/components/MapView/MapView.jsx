import React, { useRef, useEffect, useState } from 'react'
import L from 'leaflet'
import './MapView.css'

const DEFAULT_CENTER = [32.90, 13.18] // Libya (Tripoli area)
const DEFAULT_ZOOM = 11

function MapView() {
  const mapRef = useRef(null)
  const mapInstance = useRef(null)
  const markersLayer = useRef(null)
  const trailsLayer = useRef(null)
  const [positions, setPositions] = useState([])
  const [selectedRadio, setSelectedRadio] = useState(null)

  useEffect(() => {
    if (mapInstance.current) return

    mapInstance.current = L.map(mapRef.current, {
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
      zoomControl: true,
    })

    // Offline tiles served from backend /tiles/{z}/{x}/{y}.png
    L.tileLayer('/api/../tiles/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap (Offline)',
      maxZoom: 14,
      minZoom: 10,
      errorTileUrl: '',
    }).addTo(mapInstance.current)

    markersLayer.current = L.layerGroup().addTo(mapInstance.current)
    trailsLayer.current = L.layerGroup().addTo(mapInstance.current)

    return () => {
      if (mapInstance.current) {
        mapInstance.current.remove()
        mapInstance.current = null
      }
    }
  }, [])

  // Fetch GPS data
  useEffect(() => {
    fetch('/api/gps/latest')
      .then(r => r.json())
      .then(d => setPositions(d.data || []))
      .catch(() => {})

    const interval = setInterval(() => {
      fetch('/api/gps/latest')
        .then(r => r.json())
        .then(d => setPositions(d.data || []))
        .catch(() => {})
    }, 5000)

    return () => clearInterval(interval)
  }, [])

  // Update markers
  useEffect(() => {
    if (!markersLayer.current) return
    markersLayer.current.clearLayers()

    positions.forEach(pos => {
      if (!pos.latitude || !pos.longitude) return

      const icon = L.divIcon({
        className: 'radio-marker',
        html: `<div class="marker-dot" title="RID: ${pos.radio_id_dec}">
          <span class="marker-label">${pos.alias || pos.radio_id_dec}</span>
        </div>`,
        iconSize: [12, 12],
        iconAnchor: [6, 6],
      })

      const marker = L.marker([pos.latitude, pos.longitude], { icon })
        .bindPopup(`
          <div class="marker-popup">
            <strong>${pos.alias || 'Radio'} (${pos.radio_id_dec})</strong><br/>
            <span>Hex: ${pos.radio_id_hex}</span><br/>
            <span>Lat: ${pos.latitude?.toFixed(6)}</span><br/>
            <span>Lon: ${pos.longitude?.toFixed(6)}</span><br/>
            ${pos.speed_kmh != null ? `<span>Speed: ${pos.speed_kmh} km/h</span><br/>` : ''}
            ${pos.heading != null ? `<span>Heading: ${pos.heading}°</span><br/>` : ''}
            <span>Last: ${new Date(pos.timestamp).toLocaleString()}</span>
          </div>
        `)
        .on('click', () => setSelectedRadio(pos))

      markersLayer.current.addLayer(marker)
    })

    // Auto-fit to markers
    if (positions.length > 0) {
      const bounds = positions
        .filter(p => p.latitude && p.longitude)
        .map(p => [p.latitude, p.longitude])
      if (bounds.length > 0) {
        mapInstance.current?.fitBounds(bounds, { padding: [50, 50], maxZoom: 14 })
      }
    }
  }, [positions])

  // Load trail for selected radio
  useEffect(() => {
    if (!selectedRadio || !trailsLayer.current) return
    trailsLayer.current.clearLayers()

    fetch(`/api/gps/radio/${selectedRadio.radio_id_dec}`)
      .then(r => r.json())
      .then(d => {
        const points = (d.data || [])
          .filter(p => p.latitude && p.longitude)
          .map(p => [p.latitude, p.longitude])

        if (points.length > 1) {
          L.polyline(points, {
            color: '#06b6d4',
            weight: 2,
            opacity: 0.7,
            dashArray: '5, 5',
          }).addTo(trailsLayer.current)
        }
      })
      .catch(() => {})
  }, [selectedRadio])

  return (
    <div className="mapview-container">
      <div className="mapview-header">
        <h2>🗺️ Radio GPS Positions</h2>
        <span className="mapview-count">{positions.length} radios tracked</span>
      </div>
      <div className="mapview-map glass" ref={mapRef}></div>
    </div>
  )
}

export default MapView
