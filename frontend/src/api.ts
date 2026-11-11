import type { HealthState, Summary, TransactionPage, VehicleTrack, Zone } from './types'

async function readJson<T>(path: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`)
  }
  return response.json() as Promise<T>
}

export function fetchTransactions(): Promise<TransactionPage> {
  return readJson('/api/v1/transactions?page_size=50')
}

export function fetchSummary(): Promise<Summary> {
  return readJson('/api/v1/transactions/summary')
}

export async function fetchTracks(): Promise<VehicleTrack[]> {
  const body = await readJson<{ vehicles: VehicleTrack[] }>('/processor/tracks')
  return body.vehicles ?? []
}

export async function fetchZones(): Promise<Zone[]> {
  const body = await readJson<{ zones: Zone[] }>('/processor/zones')
  return body.zones ?? []
}

export async function fetchHealth(path: string): Promise<HealthState> {
  try {
    const response = await fetch(path)
    if (response.ok) return 'up'
    if (response.status === 503) return 'degraded'
    return 'down'
  } catch {
    return 'down'
  }
}
