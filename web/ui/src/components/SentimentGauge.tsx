import useSWR from 'swr'
import { fetcher } from '../lib/http'

// Aggregate BTC sentiment as a proxy for global gauge; can expand later
export function SentimentGauge({ symbol = 'BTC/USD' }: { symbol?: string }) {
  const { data } = useSWR<{ symbol: string; sent_24h: number; sent_7d: number; sent_trend: number; burst: number }>(
    `/api/sentiment?symbol=${encodeURIComponent(symbol)}`,
    fetcher,
    { refreshInterval: 5 * 60_000 }
  )

  const s = data?.sent_24h ?? 0
  const trend = data?.sent_trend ?? 0

  return (
    <div className="card bg-base-100 shadow-lg border border-secondary/40">
      <div className="card-body">
        <h2 className="card-title font-mono tracking-wide">Sentiment</h2>
        <div className="flex items-center gap-4">
          <Gauge value={s} />
          <div>
            <div className="text-xs opacity-70 font-mono">24h</div>
            <div className="text-lg font-semibold">{s.toFixed(2)}</div>
            <div className="text-xs opacity-70 font-mono">Trend</div>
            <div className={`text-lg font-semibold ${trend > 0 ? 'text-success' : trend < 0 ? 'text-error' : ''}`}>
              {trend.toFixed(2)}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function Gauge({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(100, (value + 1) * 50)) // map [-1,1]→[0,100] if using polarity
  return (
    <div className="radial-progress text-secondary" style={{
      // @ts-expect-error tailwind var
      '--value': pct,
      '--size': '6rem',
      '--thickness': '8px'
    } as any}>
      <span className="font-mono text-sm">{pct.toFixed(0)}%</span>
    </div>
  )
}


