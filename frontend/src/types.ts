export type TxStatus = 'PENDING' | 'PROCESSING' | 'SUCCESS' | 'FAILED' | 'RETRY' | string

export type Transaction = {
  id: number
  toll_event_id: string
  vehicle_id: string
  amount: number
  currency: string
  status: TxStatus
  transaction_time: string
  payment_gateway_ref: string | null
  error_message: string | null
}

export type TransactionPage = {
  items: Transaction[]
  total: number
  page: number
  page_size: number
}

export type Summary = {
  total: number
  amount_total: number
  by_status: { status: string; count: number; amount: number }[]
}

export type TrackPoint = {
  lat: number
  lon: number
  timestamp: number
  inZone: boolean
}

export type VehicleTrack = {
  vehicleId: string
  points: TrackPoint[]
}

export type Zone = {
  zoneId: string
  name: string
  ratePerKm: number
  geojson: { type: string; coordinates: number[][][] }
}

export type HealthState = 'up' | 'degraded' | 'down'
