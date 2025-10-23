import useSWR from 'swr'
import { fetcher } from '../lib/http'
import { Sparkline } from './charts/Sparkline'
import { motion } from 'framer-motion'

type SymbolData = {
  symbol: string
  regime: 'trend' | 'chop' | 'unknown'
  last_price: number
  rvol: number
  donch_upper: number
  donch_lower: number
  cmf: number
}

export function TickerGrid() {
  const { data } = useSWR<SymbolData[]>('/api/symbols', fetcher, { refreshInterval: 5000 })

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
      {(data ?? []).map(s => <TickerTile key={s.symbol} s={s} />)}
    </div>
  )
}

function TickerTile({ s }: { s: SymbolData }) {
  const regimeColor = s.regime === 'trend' ? 'badge-success' : s.regime === 'chop' ? 'badge-warning' : 'badge-ghost'
  const donchState = s.last_price > s.donch_upper ? 'Above U' : s.last_price < s.donch_lower ? 'Below L' : 'Inside'
  return (
    <motion.div whileHover={{ y: -2 }} className="card bg-base-100 border border-base-content/20 shadow">
      <div className="card-body p-4">
        <div className="flex items-center justify-between">
          <div className="font-mono font-bold">{s.symbol}</div>
          <div className={`badge ${regimeColor} badge-sm`}>{s.regime}</div>
        </div>
        <div className="text-2xl font-semibold mt-1">{fmtPrice(s.last_price)}</div>
        <div className="mt-2">
          <Sparkline symbol={s.symbol} />
        </div>
        <div className="mt-2 grid grid-cols-3 gap-2 text-xs font-mono">
          <Badge label="RVOL" value={s.rvol.toFixed(2)} color={s.rvol > 1.5 ? 'text-secondary' : ''} />
          <Badge label="CMF" value={s.cmf.toFixed(2)} color={s.cmf > 0 ? 'text-success' : s.cmf < 0 ? 'text-error' : ''} />
          <Badge label="Donch" value={donchState} />
        </div>
      </div>
    </motion.div>
  )
}

function Badge({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <div className="opacity-60">{label}</div>
      <div className={`font-semibold ${color ?? ''}`}>{value}</div>
    </div>
  )
}

function fmtPrice(v: number) {
  if (!Number.isFinite(v)) return '—'
  return v >= 100 ? v.toFixed(2) : v >= 1 ? v.toFixed(4) : v.toFixed(6)
}


