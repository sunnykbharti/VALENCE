import React from 'react'
import { Search, Bell, Mic, Sliders, ChevronDown } from 'lucide-react'

export default function Topbar({ activePage, equipmentModel, setEquipmentModel }) {
  return (
    <header className="topbar">
      <div className="topbar-title">
        <h1>{activePage === 'Overview' ? 'Smart Maintenance Operations' : activePage}</h1>
        <p>Offline Industrial Knowledge Assistant • Air-gapped Runtime</p>
      </div>

      {/* Global Search */}
      <div className="topbar-search">
        <Search size={15} className="search-icon" />
        <input
          type="text"
          placeholder="Search machines, sensors, alerts, SOPs..."
        />
      </div>

      <div className="topbar-actions">
        {/* Status Pill */}
        <div className="pill pill-green">
          <span className="dot dot-green" style={{ width: 6, height: 6 }} />
          <span>Live Production</span>
        </div>

        {/* Plant / Unit Selector */}
        <div className="pill pill-cyan" style={{ cursor: 'pointer' }}>
          <span>Plant 01 - Detroit</span>
          <ChevronDown size={14} />
        </div>

        {/* Audio / Mic control */}
        <button className="icon-btn" title="Voice Input (Disabled in air-gap)">
          <Mic size={16} />
        </button>

        {/* Quick model filter indicator */}
        <button className="icon-btn" title="Model Filter">
          <Sliders size={16} />
        </button>

        {/* Notifications */}
        <button className="icon-btn" style={{ position: 'relative' }}>
          <Bell size={16} />
          <span
            style={{
              position: 'absolute',
              top: '5px',
              right: '5px',
              width: '6px',
              height: '6px',
              background: 'var(--accent-red)',
              borderRadius: '50%',
            }}
          />
        </button>

        {/* User Avatar */}
        <div className="avatar" title="Plant Engineer">
          PE
        </div>
      </div>
    </header>
  )
}

