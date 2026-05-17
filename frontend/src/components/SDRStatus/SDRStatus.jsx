import React, { useState, useEffect } from 'react'
import './SDRStatus.css'

function SDRStatus() {
  const [devices, setDevices] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchDevices = () => {
      fetch('/api/sdr')
        .then(r => r.json())
        .then(d => { setDevices(d.data || []); setLoading(false); })
        .catch(() => setLoading(false))
    }
    fetchDevices()
    const interval = setInterval(fetchDevices, 3000)
    return () => clearInterval(interval)
  }, [])

  const getModeColor = (mode) => {
    switch (mode) {
      case 'SWEEP': return 'var(--accent-cyan)'
      case 'PINNED': return 'var(--accent-green)'
      case 'DISCOVERY': return 'var(--accent-amber)'
      case 'ERROR': return 'var(--accent-red)'
      default: return 'var(--text-muted)'
    }
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'ACTIVE': return '🟢'
      case 'DISCONNECTED': return '🔴'
      case 'ERROR': return '⚠️'
      case 'INITIALIZING': return '🟡'
      default: return '⚪'
    }
  }

  if (loading) {
    return <div className="sdr-loading"><div className="spinner"></div><p>Loading SDR devices...</p></div>
  }

  return (
    <div className="sdr-container">
      <div className="sdr-header">
        <h2>📻 SDR Devices</h2>
        <span className="sdr-count">{devices.length} device(s)</span>
      </div>
      {devices.length === 0 ? (
        <div className="sdr-empty glass">
          <p>No SDR devices registered yet.</p>
          <p className="empty-hint">Devices will appear once the middleware connects.</p>
        </div>
      ) : (
        <div className="sdr-grid">
          {devices.map(dev => (
            <div key={dev.id} className="sdr-card glass animate-fade-in">
              <div className="sdr-card-header">
                <span className="sdr-status-icon">{getStatusIcon(dev.status)}</span>
                <div>
                  <h3>{dev.label || dev.serial}</h3>
                  <span className="sdr-type">{dev.device_type}</span>
                </div>
              </div>
              <div className="sdr-card-body">
                <div className="sdr-field">
                  <span className="field-label">Serial</span>
                  <span className="field-value mono">{dev.serial}</span>
                </div>
                <div className="sdr-field">
                  <span className="field-label">Mode</span>
                  <span className="field-value mode-badge" style={{ color: getModeColor(dev.mode) }}>
                    {dev.mode}
                  </span>
                </div>
                <div className="sdr-field">
                  <span className="field-label">Frequency</span>
                  <span className="field-value mono">
                    {dev.assigned_freq ? `${dev.assigned_freq.toFixed(4)} MHz` : '—'}
                  </span>
                </div>
                <div className="sdr-field">
                  <span className="field-label">Sample Rate</span>
                  <span className="field-value mono">{(dev.sample_rate / 1e6).toFixed(1)} MS/s</span>
                </div>
                <div className="sdr-field">
                  <span className="field-label">Gain</span>
                  <span className="field-value mono">{dev.gain_db} dB</span>
                </div>
                <div className="sdr-field">
                  <span className="field-label">Last Heartbeat</span>
                  <span className="field-value">
                    {dev.last_heartbeat ? new Date(dev.last_heartbeat).toLocaleTimeString() : '—'}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default SDRStatus
