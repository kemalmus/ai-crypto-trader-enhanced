import { useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { KeyLogsStream } from './components/KeyLogsStream'
import { TickerGrid } from './components/TickerGrid'
import { TradesPanel } from './components/TradesPanel'
import { OverviewCard } from './components/OverviewCard'
import { SentimentGauge } from './components/SentimentGauge'

export default function App() {
  return (
    <div className="min-h-screen grid grid-cols-1 xl:grid-cols-[360px_minmax(0,1fr)_420px] gap-4 p-4">
      <div className="space-y-4">
        <OverviewCard />
        <SentimentGauge />
      </div>
      <div className="space-y-4">
        <KeyLogsStream />
        <TickerGrid />
      </div>
      <div className="space-y-4">
        <TradesPanel />
      </div>
    </div>
  )
}


