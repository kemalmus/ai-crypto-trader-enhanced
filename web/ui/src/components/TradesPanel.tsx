import useSWR from 'swr'
import { fetcher } from '../lib/http'

type Trade = {
  id: number
  symbol: string
  side: string
  qty: number
  entry_ts: string
  entry_px: number
  exit_ts?: string | null
  exit_px?: number | null
  pnl?: number | null
  fees: number
  slippage_bps: number
  reason?: string | null
}

export function TradesPanel() {
  const { data } = useSWR<Trade[]>(`/api/trades?limit=50`, fetcher, { refreshInterval: 10000 })
  return (
    <div className="card bg-base-100 shadow-lg border border-info/40">
      <div className="card-body">
        <h2 className="card-title font-mono tracking-wide">Trades</h2>
        <div className="overflow-x-auto">
          <table className="table table-zebra table-sm">
            <thead>
              <tr className="font-mono text-xs opacity-70">
                <th>Time</th>
                <th>Symbol</th>
                <th>Side</th>
                <th>Qty</th>
                <th>Entry</th>
                <th>Exit</th>
                <th>PnL</th>
              </tr>
            </thead>
            <tbody>
              {(data ?? []).map(t => (
                <tr key={t.id}>
                  <td>{new Date(t.entry_ts).toLocaleTimeString()}</td>
                  <td className="font-mono">{t.symbol}</td>
                  <td className={`font-semibold ${t.side === 'long' ? 'text-success' : 'text-error'}`}>{t.side}</td>
                  <td>{t.qty}</td>
                  <td>{fmtPx(t.entry_px)}</td>
                  <td>{t.exit_px ? fmtPx(t.exit_px) : '—'}</td>
                  <td className={numColor(t.pnl)}>{fmtUsd(t.pnl)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function fmtUsd(v?: number | null) {
  const n = v ?? 0
  return n.toLocaleString(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 2 })
}
function fmtPx(v: number) {
  return v >= 100 ? v.toFixed(2) : v >= 1 ? v.toFixed(4) : v.toFixed(6)
}
function numColor(v?: number | null) {
  if (v == null) return ''
  if (v > 0) return 'text-success'
  if (v < 0) return 'text-error'
  return ''
}


