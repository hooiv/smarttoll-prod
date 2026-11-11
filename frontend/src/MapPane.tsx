import { useEffect, useRef } from 'react'
import { CircleMarker, MapContainer, Polygon, Polyline, TileLayer, useMap } from 'react-leaflet'
import type { LatLngExpression } from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { VehicleTrack, Zone } from './types'

type Props = {
  zones: Zone[]
  tracks: VehicleTrack[]
  selectedId: string | null
}

function ringFromZone(zone: Zone): LatLngExpression[] {
  const ring = zone.geojson?.coordinates?.[0] ?? []
  return ring.map(([lon, lat]) => [lat, lon] as LatLngExpression)
}

function FitZones({ zones }: { zones: Zone[] }) {
  const map = useMap()
  const signature = zones.map((zone) => zone.zoneId).join('|')
  useEffect(() => {
    const points = zones.flatMap(ringFromZone) as [number, number][]
    if (points.length === 0) return
    map.fitBounds(points, { padding: [28, 28], maxZoom: 11 })
  }, [map, signature])
  return null
}

function FitSelected({ vehicleId, positions }: { vehicleId: string | null; positions: LatLngExpression[] }) {
  const map = useMap()
  const positionsRef = useRef(positions)
  positionsRef.current = positions
  useEffect(() => {
    const current = positionsRef.current
    if (!vehicleId || current.length === 0) return
    map.fitBounds(current as [number, number][], { padding: [32, 32], maxZoom: 16 })
  }, [map, vehicleId])
  return null
}

export function MapPane({ zones, tracks, selectedId }: Props) {
  const selected = tracks.find((track) => track.vehicleId === selectedId)
  const focus: LatLngExpression[] = selected
    ? selected.points.map((point) => [point.lat, point.lon])
    : []

  return (
    <MapContainer
      center={[28.4, 77.0]}
      zoom={8}
      scrollWheelZoom={false}
      style={{ height: '100%', width: '100%' }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {zones.map((zone) => {
        const ring = ringFromZone(zone)
        if (ring.length === 0) return null
        return (
          <Polygon
            key={zone.zoneId}
            positions={ring}
            pathOptions={{ color: '#0c6b52', weight: 2, fillColor: '#0c6b52', fillOpacity: 0.15 }}
          />
        )
      })}
      {tracks.map((track) => {
        const positions = track.points.map((point) => [point.lat, point.lon] as LatLngExpression)
        const active = track.vehicleId === selectedId
        return (
          <Polyline
            key={track.vehicleId}
            positions={positions}
            pathOptions={{ color: active ? '#14171a' : '#8b939c', weight: active ? 3 : 2 }}
          />
        )
      })}
      {tracks.map((track) => {
        const last = track.points[track.points.length - 1]
        if (!last) return null
        const active = track.vehicleId === selectedId
        return (
          <CircleMarker
            key={`${track.vehicleId}-last`}
            center={[last.lat, last.lon]}
            radius={active ? 7 : 5}
            pathOptions={{ color: '#14171a', fillColor: last.inZone ? '#0c6b52' : '#ffffff', fillOpacity: 1, weight: 2 }}
          />
        )
      })}
      <FitZones zones={zones} />
      <FitSelected vehicleId={selectedId} positions={focus} />
    </MapContainer>
  )
}
