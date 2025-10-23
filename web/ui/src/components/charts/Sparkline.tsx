import { useEffect, useRef } from 'react'
import useSWR from 'swr'
import { fetcher } from '../../lib/http'

type Candle = { ts: string; c: number }

export function Sparkline({ symbol }: { symbol: string }) {
  const { data } = useSWR<Candle[]>(`/api/candles?symbol=${encodeURIComponent(symbol)}&tf=5m&limit=288`, fetcher, {
    refreshInterval: 15000,
  })
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!data || !ref.current) return
    const el = ref.current
    const width = el.clientWidth || 200
    const height = 40
    const values = data.map(d => d.c)
    const min = Math.min(...values)
    const max = Math.max(...values)
    const norm = (v: number) => (1 - (v - min) / Math.max(1e-9, max - min)) * (height - 2) + 1
    const step = Math.max(1, Math.floor(values.length / width))
    const points: string[] = []
    for (let i = 0; i < values.length; i += step) {
      const x = Math.round((i / (values.length - 1)) * (width - 2)) + 1
      const y = Math.round(norm(values[i]))
      points.push(`${x},${y}`)
    }
    el.innerHTML = `<svg width="100%" height="${height}" viewBox="0 0 ${width} ${height}">
      <polyline fill="none" stroke="hsl(var(--p))" stroke-width="2" points="${points.join(' ')}" />
    </svg>`
  }, [data])

  return <div ref={ref} className="w-full" />
}


