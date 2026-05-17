import React, { useState, useEffect } from 'react'
import Header from './components/common/Header'
import Sidebar from './components/common/Sidebar'
import LiveLog from './components/LiveLog/LiveLog'
import TopologyGraph from './components/TopologyGraph/TopologyGraph'
import MapView from './components/MapView/MapView'
import SDRStatus from './components/SDRStatus/SDRStatus'
import AudioPlayer from './components/AudioPlayer/AudioPlayer'
import { useWebSocket } from './hooks/useWebSocket'
import './App.css'

const TABS = [
  { id: 'live', label: 'Live Feed', icon: '📡' },
  { id: 'topology', label: 'Topology', icon: '🔗' },
  { id: 'map', label: 'Map', icon: '🗺️' },
  { id: 'sdr', label: 'SDR Status', icon: '📻' },
]

function App() {
  const [activeTab, setActiveTab] = useState('live')
  const [stats, setStats] = useState({ signals: 0, radios: 0, gps: 0, alerts: 0 })
  const { messages, connected } = useWebSocket()

  useEffect(() => {
    // Fetch initial stats
    fetch('/api/signals?limit=1')
      .then(r => r.json())
      .then(d => setStats(s => ({ ...s, signals: d.pagination?.total || 0 })))
      .catch(() => {})
    fetch('/api/radios')
      .then(r => r.json())
      .then(d => setStats(s => ({ ...s, radios: d.data?.length || 0 })))
      .catch(() => {})
    fetch('/api/gps/latest')
      .then(r => r.json())
      .then(d => setStats(s => ({ ...s, gps: d.data?.length || 0 })))
      .catch(() => {})
  }, [])

  // Update stats on new WebSocket messages
  useEffect(() => {
    if (messages.length > 0) {
      const last = messages[messages.length - 1]
      if (last.type === 'signal_log') setStats(s => ({ ...s, signals: s.signals + 1 }))
      if (last.type === 'gps_event') setStats(s => ({ ...s, gps: s.gps + 1 }))
    }
  }, [messages])

  const renderContent = () => {
    switch (activeTab) {
      case 'live': return <LiveLog messages={messages} />
      case 'topology': return <TopologyGraph />
      case 'map': return <MapView />
      case 'sdr': return <SDRStatus />
      default: return <LiveLog messages={messages} />
    }
  }

  return (
    <div className="app-container">
      <Header connected={connected} stats={stats} />
      <div className="app-body">
        <Sidebar tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab} />
        <main className="app-content">
          {renderContent()}
        </main>
      </div>
      <AudioPlayer messages={messages} />
    </div>
  )
}

export default App
