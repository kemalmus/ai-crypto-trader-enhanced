import useSWR from 'swr'
import { fetcher } from '../lib/http'

type Overview = {
  nav_usd: number
  realized_pnl: number
  unrealized_pnl: number
  dd_pct: number
  open_positions_count: number
  last_cycle_ts?: string | null
  cycle_latency_ms?: number | null
}

export function OverviewCard() {
  const { data } = useSWR<Overview>('/api/overview', fetcher, { refreshInterval: 10000 })

  return (
    <div className="card bg-base-100 shadow-lg border border-primary/40">
      <div className="card-body">
        <h2 className="card-title font-mono tracking-wide">Overview</h2>
        <div className="grid grid-cols-2 gap-4">
          <Metric label="NAV" value={fmtUsd(data?.nav_usd)} accent="text-primary" />
          <Metric label="Drawdown" value={`${(data?.dd_pct ?? 0).toFixed(2)}%`} accent="text-secondary" />
          <Metric label="Realized PnL" value={fmtUsd(data?.realized_pnl)} accent={numColor(data?.realized_pnl)} />
          <Metric label="Unrealized PnL" value={fmtUsd(data?.unrealized_pnl)} accent={numColor(data?.unrealized_pnl)} />
          <Metric label="Open Positions" value={String(data?.open_positions_count ?? 0)} />
          <Metric label="Last Cycle" value={data?.last_cycle_ts ? new Date(data.last_cycle_ts).toLocaleTimeString() : '—'} />
        </div>
      </div>
    </div>
  )
}

function Metric({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div>
      <div className="text-xs opacity-70 font-mono">{label}</div>
      <div className={`text-lg font-semibold ${accent ?? ''}`}>{value}</div>
    </div>
  )
}

function fmtUsd(v?: number) {
  const n = v ?? 0
  return n.toLocaleString(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 2 })
}

function numColor(v?: number) {
  if (v == null) return ''
  if (v > 0) return 'text-success'
  if (v < 0) return 'text-error'
  return ''
}


