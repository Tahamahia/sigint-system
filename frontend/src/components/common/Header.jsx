import React from 'react'
import './Header.css'

function Header({ connected, stats }) {
  return (
    <header className="header glass">
      <div className="header-left">
        <div className="header-logo">
          <span className="logo-icon">◉</span>
          <h1>SIGINT<span className="logo-accent">Dashboard</span></h1>
        </div>
        <div className={`connection-badge ${connected ? 'connected' : 'disconnected'}`}>
          <span className="pulse-dot"></span>
          {connected ? 'LIVE' : 'OFFLINE'}
        </div>
      </div>
      <div className="header-stats">
        <div className="stat-item">
          <span className="stat-value">{stats.signals.toLocaleString()}</span>
          <span className="stat-label">Signals</span>
        </div>
        <div className="stat-item">
          <span className="stat-value">{stats.radios}</span>
          <span className="stat-label">Radios</span>
        </div>
        <div className="stat-item">
          <span className="stat-value">{stats.gps}</span>
          <span className="stat-label">GPS Fixes</span>
        </div>
      </div>
    </header>
  )
}

export default Header
