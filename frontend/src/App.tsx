import { useEffect, useMemo, useState } from 'react'
import { fetchHealth, fetchSummary, fetchTransactions } from './api'
import { MapPane } from './MapPane'
import type { HealthState, Summary, Transaction, VehicleTrack, Zone } from './types'

type HealthMap = Record<string, HealthState>

const HEALTH_CHECKS: { id: string; label: string; path: string }[] = [
  { id: 'billing-live', label: 'Billing live', path: '/api/v1/health/live' },
  { id: 'billing-ready', label: 'Billing ready', path: '/api/v1/health/ready' },
  { id: 'processor-live', label: 'Processor live', path: '/processor/health/live' },
  { id: 'processor-ready', label: 'Processor ready', path: '/processor/health/ready' },
  { id: 'simulator-live', label: 'Simulator live', path: '/simulator/health/live' },
  { id: 'simulator-ready', label: 'Simulator ready', path: '/simulator/health/ready' },
]

const money = (amount: number, currency = 'INR') =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency, maximumFractionDigits: 2 }).format(amount)

const kolkataTime = (iso: string) =>
  new Date(iso).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', hour12: true })

function statusClass(status: string) {
  if (status === 'SUCCESS' || status === 'up') return 'up'
  if (status === 'FAILED' || status === 'down') return 'down'
  return 'degraded'
}

export default function App() {
  const [transactions, setTransactions] = useState<Transaction[] | null>(null)
  const [total, setTotal] = useState(0)
  const [summary, setSummary] = useState<Summary | null>(null)
  const [tracks, setTracks] = useState<VehicleTrack[]>([])
  const [zones, setZones] = useState<Zone[]>([])
  const [health, setHealth] = useState<HealthMap>({})
  const [ledgerError, setLedgerError] = useState<string | null>(null)
  const [summaryError, setSummaryError] = useState<string | null>(null)
  const [mapError, setMapError] = useState<string | null>(null)
  const [zoneError, setZoneError] = useState<string | null>(null)
  const [billingLink, setBillingLink] = useState<'connecting' | 'live' | 'reconnecting'>('connecting')
  const [mapLink, setMapLink] = useState<'connecting' | 'live' | 'reconnecting'>('connecting')
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  useEffect(() => {
    let stop = false
    const refreshLedger = async () => {
      try {
        const page = await fetchTransactions()
        if (stop) return
        setTransactions(page.items)
        setTotal(page.total)
        setLedgerError(null)
      } catch (error) {
        if (!stop) setLedgerError(error instanceof Error ? error.message : 'Ledger request failed')
      }
      try {
        const next = await fetchSummary()
        if (stop) return
        setSummary(next)
        setSummaryError(null)
      } catch (error) {
        if (!stop) setSummaryError(error instanceof Error ? error.message : 'Summary request failed')
      }
    }
    const refreshHealth = async () => {
      const checks = await Promise.all(
        HEALTH_CHECKS.map(async (check) => [check.id, await fetchHealth(check.path)] as const),
      )
      if (!stop) setHealth(Object.fromEntries(checks))
    }
    void refreshLedger()
    void refreshHealth()
    const healthTimer = window.setInterval(() => { void refreshHealth() }, 5000)

    let billingRetry = 0
    let mapRetry = 0
    let billingSource: EventSource | null = null
    let mapSource: EventSource | null = null

    const openBilling = () => {
      billingSource?.close()
      const source = new EventSource('/api/v1/stream')
      billingSource = source
      source.onopen = () => { if (!stop) setBillingLink('live') }
      source.addEventListener('hello', () => { void refreshLedger() })
      source.addEventListener('transaction', () => { void refreshLedger() })
      let closed = false
      source.onerror = () => {
        if (closed) return
        closed = true
        source.close()
        if (stop) return
        setBillingLink('reconnecting')
        billingRetry = window.setTimeout(openBilling, 2000)
      }
    }
    const openMap = () => {
      mapSource?.close()
      const source = new EventSource('/processor/stream')
      mapSource = source
      source.onopen = () => { if (!stop) setMapLink('live') }
      source.addEventListener('map', (event) => {
        if (stop) return
        try {
          const body = JSON.parse((event as MessageEvent<string>).data) as {
            vehicles?: VehicleTrack[]
            zones?: Zone[]
          }
          setTracks(body.vehicles ?? [])
          setZones(body.zones ?? [])
          setMapError(null)
          setZoneError(body.zones && body.zones.length > 0 ? null : 'The processor returned no toll zones.')
        } catch {
          setMapError('The map stream sent a payload the console could not read.')
        }
      })
      let closed = false
      source.onerror = () => {
        if (closed) return
        closed = true
        source.close()
        if (stop) return
        setMapLink('reconnecting')
        setMapError('Map stream disconnected. Reconnecting.')
        mapRetry = window.setTimeout(openMap, 2000)
      }
    }
    openBilling()
    openMap()
    return () => {
      stop = true
      window.clearInterval(healthTimer)
      window.clearTimeout(billingRetry)
      window.clearTimeout(mapRetry)
      billingSource?.close()
      mapSource?.close()
    }
  }, [])

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    const rows = transactions ?? []
    if (!needle) return rows
    return rows.filter((row) => row.vehicle_id.toLowerCase().includes(needle))
  }, [transactions, query])

  const selectedRows = selectedId ? (transactions ?? []).filter((row) => row.vehicle_id === selectedId) : []
  const selectedTrack = tracks.find((track) => track.vehicleId === selectedId)
  const success = summary?.by_status.find((row) => row.status === 'SUCCESS')
  const successRate = summary && summary.total > 0 && success
    ? Math.round((success.count / summary.total) * 100)
    : null

  return (
    <div className="app">
      <a className="skip" href="#ledger">Skip to transactions</a>
      <header className="topbar">
        <div className="brand">
          <strong>SmartToll</strong>
          <span>Operations</span>
          <span className={`pill ${billingLink === 'live' && mapLink === 'live' ? 'up' : 'degraded'}`} role="status">
            {billingLink === 'live' && mapLink === 'live' ? 'live' : billingLink === 'connecting' && mapLink === 'connecting' ? 'connecting' : 'reconnecting'}
          </span>
        </div>
        <nav aria-label="Page">
          <a href="#map">Map</a>
          <a href="#ledger">Ledger</a>
          <a href="#about">About</a>
          <a href="http://localhost:8001/docs">API</a>
          <a href="http://localhost:3001/d/smarttoll/smarttoll">Grafana</a>
        </nav>
      </header>
      <main className="wrap">
        <section className="stats" aria-label="Totals">
          <article className="card">
            <h2>Transactions</h2>
            <p className="stat-value">{summary ? summary.total : 'n/a'}</p>
            <p className="stat-note">Rows in Postgres</p>
          </article>
          <article className="card">
            <h2>Collected</h2>
            <p className="stat-value">{summary ? money(summary.amount_total) : 'n/a'}</p>
            <p className="stat-note">Sum of stored amounts</p>
          </article>
          <article className="card">
            <h2>Success</h2>
            <p className="stat-value">{successRate === null ? 'n/a' : `${successRate}%`}</p>
            <p className="stat-note">{success ? `${success.count} succeeded` : 'No charges yet'}</p>
          </article>
          <article className="card">
            <h2>Vehicles on the map</h2>
            <p className="stat-value">{tracks.length}</p>
            <p className="stat-note">Recent GPS trails, in memory</p>
          </article>
        </section>

        <section className="split" id="map">
          <div className="panel">
            <header>
              <h2>NH-48 · Delhi to Neemrana</h2>
              <span className="muted">OpenStreetMap · filled dot means inside the zone</span>
            </header>
            <div className="map-frame" role="region" aria-label="Map of the toll zone and vehicle tracks">
              <MapPane zones={zones} tracks={tracks} selectedId={selectedId} />
            </div>
            {(mapError || zoneError) && <div className="body"><p className="banner">{mapError ?? zoneError}</p></div>}
          </div>
          <div className="panel">
            <header><h2>Pipeline</h2></header>
            <div className="body">
              <ul className="health-list">
                {HEALTH_CHECKS.map((check) => {
                  const state = health[check.id]
                  return (
                    <li key={check.id}>
                      <span>{check.label}</span>
                      <span className={`pill ${state ? statusClass(state) : ''}`}>{state ?? 'n/a'}</span>
                    </li>
                  )
                })}
              </ul>
              <h2 style={{ marginTop: 18 }}>Payment status</h2>
              {summary && summary.by_status.length > 0 ? (
                <div className="bars">
                  {summary.by_status.map((row) => (
                    <div className="bar-row" key={row.status}>
                      <span>{row.status}</span>
                      <div className="bar-track" aria-hidden="true">
                        <div className={`bar-fill ${row.status}`} style={{ width: `${summary.total ? (row.count / summary.total) * 100 : 0}%` }} />
                      </div>
                      <span className="mono">{row.count} · {money(row.amount)}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className={summaryError ? 'banner' : 'muted'}>
                  {summaryError ? `Payment totals are unavailable. ${summaryError}` : 'No payment outcomes yet.'}
                </p>
              )}
            </div>
          </div>
        </section>

        <section className="panel" id="ledger">
          <div className="ledger-head">
            <h2>Recent transactions{transactions ? ` · ${total}` : ''}</h2>
            <label>
              <span className="muted">Vehicle </span>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Filter by vehicle id"
                aria-label="Filter transactions by vehicle id"
              />
            </label>
          </div>
          {ledgerError && <div className="body"><p className="banner">Could not load the ledger. {ledgerError}</p></div>}
          {transactions === null && !ledgerError && <p className="empty">Loading transactions…</p>}
          {transactions && filtered.length === 0 && <p className="empty">No transactions match. A charge is written when a vehicle leaves Kherki Daula or Shahjahanpur.</p>}
          {filtered.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Vehicle</th>
                  <th className="right">Amount</th>
                  <th>Status</th>
                  <th>Gateway ref</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => (
                  <tr
                    key={row.id}
                    aria-selected={row.vehicle_id === selectedId}
                    tabIndex={0}
                    onClick={() => setSelectedId(row.vehicle_id)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        setSelectedId(row.vehicle_id)
                      }
                    }}
                  >
                    <td className="mono">{kolkataTime(row.transaction_time)}</td>
                    <td>{row.vehicle_id}</td>
                    <td className="right mono">{money(Number(row.amount), row.currency)}</td>
                    <td><span className={`pill ${statusClass(row.status)}`}>{row.status}</span></td>
                    <td className="mono">{row.payment_gateway_ref ?? 'n/a'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {selectedId && (
            <div className="body">
              <h2>{selectedId}</h2>
              <dl className="detail">
                <dt>Charges in view</dt>
                <dd>{selectedRows.length}</dd>
                <dt>Recent GPS points</dt>
                <dd>{selectedTrack ? selectedTrack.points.length : 'none in the current trail'}</dd>
                <dt>Last fix</dt>
                <dd className="mono">
                  {selectedTrack?.points.length
                    ? `${selectedTrack.points.at(-1)?.lat.toFixed(5)}, ${selectedTrack.points.at(-1)?.lon.toFixed(5)}`
                    : 'n/a'}
                </dd>
                <dt>Last error</dt>
                <dd>{selectedRows.find((row) => row.error_message)?.error_message ?? 'n/a'}</dd>
              </dl>
            </div>
          )}
        </section>

        <section className="panel about" id="about">
          <header><h2>About this project</h2></header>
          <div className="body">
            <p>
              SmartToll follows NH-48 from Mahipalpur in Delhi to the Shahjahanpur plaza near Neemrana. Only two booths on that drive still collect a car toll: Kherki Daula and Shahjahanpur. Sirhaul was removed in 2014, and the IGI plaza at Mahipalpur stopped charging cars in November 2025. Kukdola, the planned replacement for Kherki Daula, is not open yet.
            </p>
            <p>
              The map trail is a short in-memory buffer on the processor, capped so a demo cannot grow without bound. The ledger and the payment breakdown are Postgres. Health is the same live and ready endpoints the containers use. The API key is injected by nginx and is not in the browser bundle.
            </p>
            <p>
              Payment is a mock gateway unless <span className="mono">PAYMENT_GATEWAY=stripe</span> and a Stripe test key are set. There is no card network in the default stack.
            </p>
          </div>
        </section>
      </main>
    </div>
  )
}
