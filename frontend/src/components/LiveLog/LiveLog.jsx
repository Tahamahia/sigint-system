import React, { useRef, useEffect, useState } from 'react'
import './LiveLog.css'

const PROTOCOL_COLORS = {
  DMR: 'var(--accent-cyan)',
  TETRA: 'var(--accent-magenta)',
  P25: 'var(--accent-amber)',
  P25_P1: 'var(--accent-amber)',
  P25_P2: 'var(--accent-amber)',
  NXDN: 'var(--accent-green)',
  UNKNOWN: 'var(--text-muted)',
}

function LiveLog({ messages }) {
  const containerRef = useRef(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const [filter, setFilter] = useState('')
  const [protocolFilter, setProtocolFilter] = useState('ALL')

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [messages, autoScroll])

  const handleScroll = () => {
    if (!containerRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 50)
  }

  const filtered = messages.filter(m => {
    if (protocolFilter !== 'ALL') {
      const proto = m.data?.protocol_guess || m.data?.protocol || ''
      if (proto !== protocolFilter) return false
    }
    if (filter) {
      const str = JSON.stringify(m.data).toLowerCase()
      if (!str.includes(filter.toLowerCase())) return false
    }
    return true
  })

  const formatTime = (ts) => {
    try {
      return new Date(ts).toLocaleTimeString('en-US', { hour12: false, fractionalSecondDigits: 1 })
    } catch { return ts }
  }

  return (
    <div className="livelog-container">
      <div className="livelog-header">
        <h2>📡 Live Signal Feed</h2>
        <div className="livelog-controls">
          <select
            id="protocol-filter"
            value={protocolFilter}
            onChange={e => setProtocolFilter(e.target.value)}
            className="filter-select"
          >
            <option value="ALL">All Protocols</option>
            <option value="DMR">DMR</option>
            <option value="TETRA">TETRA</option>
            <option value="P25">P25</option>
          </select>
          <input
            id="search-filter"
            type="text"
            placeholder="Search..."
            value={filter}
            onChange={e => setFilter(e.target.value)}
            className="filter-input"
          />
          <button
            id="autoscroll-toggle"
            className={`scroll-btn ${autoScroll ? 'active' : ''}`}
            onClick={() => setAutoScroll(!autoScroll)}
          >
            {autoScroll ? '⏬ Auto' : '⏸ Paused'}
          </button>
        </div>
      </div>
      <div
        className="livelog-feed glass"
        ref={containerRef}
        onScroll={handleScroll}
      >
        {filtered.length === 0 ? (
          <div className="livelog-empty">
            <span className="empty-icon">📡</span>
            <p>Waiting for signals...</p>
            <p className="empty-hint">The middleware will push events here in real-time</p>
          </div>
        ) : (
          filtered.map((msg, i) => (
            <LogEntry key={i} message={msg} formatTime={formatTime} />
          ))
        )}
      </div>
    </div>
  )
}

function LogEntry({ message, formatTime }) {
  const { type, data, timestamp } = message
  const protocol = data?.protocol_guess || data?.protocol || 'UNKNOWN'
  const color = PROTOCOL_COLORS[protocol] || PROTOCOL_COLORS.UNKNOWN

  if (type === 'signal_log') {
    return (
      <div className="log-entry animate-slide-in" style={{ borderLeftColor: color }}>
        <span className="log-time">{formatTime(timestamp)}</span>
        <span className="log-proto" style={{ color }}>{protocol}</span>
        <span className="log-freq">{data.frequency?.toFixed(4)} MHz</span>
        <span className="log-snr">SNR {data.snr_db?.toFixed(1)} dB</span>
        <span className="log-power">{data.power_dbm?.toFixed(0)} dBm</span>
      </div>
    )
  }

  if (type === 'metadata') {
    return (
      <div className="log-entry log-metadata animate-slide-in" style={{ borderLeftColor: color }}>
        <span className="log-time">{formatTime(timestamp)}</span>
        <span className="log-proto" style={{ color }}>{data.protocol || protocol}</span>
        <span className="log-rid">RID: {data.radio_id}</span>
        <span className="log-tg">TG: {data.talkgroup || '—'}</span>
        <span className={`log-calltype ${data.call_type?.toLowerCase()}`}>{data.call_type}</span>
        <span className="log-slot">TS{data.time_slot}</span>
        {data.encrypted && <span className="log-enc">🔒 ENC</span>}
      </div>
    )
  }

  if (type === 'gps_event') {
    return (
      <div className="log-entry log-gps animate-slide-in" style={{ borderLeftColor: 'var(--accent-green)' }}>
        <span className="log-time">{formatTime(timestamp)}</span>
        <span className="log-gps-icon">📍</span>
        <span className="log-rid">RID: {data.radio_id}</span>
        <span className="log-coords">{data.latitude?.toFixed(4)}, {data.longitude?.toFixed(4)}</span>
        {data.speed_kmh != null && <span className="log-speed">{data.speed_kmh?.toFixed(0)} km/h</span>}
      </div>
    )
  }

  return (
    <div className="log-entry animate-slide-in">
      <span className="log-time">{formatTime(timestamp)}</span>
      <span className="log-type">{type}</span>
      <span className="log-raw">{JSON.stringify(data).slice(0, 80)}</span>
    </div>
  )
}

export default LiveLog
