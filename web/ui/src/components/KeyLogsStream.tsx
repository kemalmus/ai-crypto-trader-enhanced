import { useEffect, useMemo, useRef, useState } from 'react'
import { Virtuoso } from 'react-virtuoso'

type LogEvent = {
  id: number
  ts: string
  level: string
  tags: string[]
  symbol?: string | null
  action?: string | null
  payload?: Record<string, any>
}

const IMPORTANT_TAGS = new Set(['SIGNAL', 'PROPOSAL', 'CONSULTANT', 'VALIDATION', 'TRADE', 'EXIT', 'RISK'])

export function KeyLogsStream() {
  const [events, setEvents] = useState<LogEvent[]>([])
  const lastIdRef = useRef<number | null>(null)

  useEffect(() => {
    const url = `/api/logs/stream${lastIdRef.current ? `?last_id=${lastIdRef.current}` : ''}`
    const es = new EventSource(url)
    es.onmessage = (ev) => {
      try {
        const data: LogEvent = JSON.parse(ev.data)
        lastIdRef.current = data.id
        if (data.tags?.some(t => IMPORTANT_TAGS.has(t))) {
          setEvents(prev => [...prev.slice(-500), data])
        }
      } catch {}
    }
    es.onerror = () => {
      es.close()
      // simple backoff reconnect
      setTimeout(() => {
        lastIdRef.current && setEvents(e => e)
      }, 1000)
    }
    return () => es.close()
  }, [])

  return (
    <div className="card bg-base-100 shadow-lg border border-accent/40 h-[360px]">
      <div className="card-body">
        <h2 className="card-title font-mono tracking-wide">Key Logs</h2>
        <div className="h-full">
          <Virtuoso
            data={events}
            itemContent={(index, item) => <LogRow item={item} />}
          />
        </div>
      </div>
    </div>
  )
}

function LogRow({ item }: { item: LogEvent }) {
  const ts = new Date(item.ts).toLocaleTimeString()
  const color = item.level === 'ERROR' ? 'text-error' : item.level === 'WARN' ? 'text-warning' : 'text-success'
  const tag = item.tags?.[0] ?? ''
  return (
    <div className="font-mono text-sm py-1 border-b border-base-200/40">
      <span className="opacity-60">[{ts}]</span>{' '}
      <span className={`${color}`}>{tag}</span>{' '}
      {item.action && <span className="badge badge-ghost badge-sm mr-2">{item.action}</span>}
      {item.symbol && <span className="text-primary">{item.symbol}</span>}
      {item.payload && item.payload.regime && (
        <span className="ml-2 opacity-70">regime {String(item.payload.regime)}</span>
      )}
    </div>
  )
}


