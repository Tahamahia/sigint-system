import React from 'react'
import './Sidebar.css'

function Sidebar({ tabs, activeTab, onTabChange }) {
  return (
    <nav className="sidebar glass">
      {tabs.map(tab => (
        <button
          key={tab.id}
          id={`tab-${tab.id}`}
          className={`sidebar-btn ${activeTab === tab.id ? 'active' : ''}`}
          onClick={() => onTabChange(tab.id)}
          title={tab.label}
        >
          <span className="sidebar-icon">{tab.icon}</span>
          <span className="sidebar-label">{tab.label}</span>
        </button>
      ))}
    </nav>
  )
}

export default Sidebar
