import React from 'react'
import { Activity, Users, AlertOctagon, Clock, Sparkles, CheckCircle2 } from 'lucide-react'

export default function BottomBar({ useMock }) {
  return (
    <footer className="bottom-bar">
      <div className="bottom-stat">
        <Activity size={14} className="bottom-icon" />
        <div>
          <div className="bottom-label">Active Work Orders</div>
          <div className="bottom-value">128</div>
        </div>
      </div>

      <div className="bottom-stat">
        <Users size={14} className="bottom-icon" />
        <div>
          <div className="bottom-label">Available Techs</div>
          <div className="bottom-value">34</div>
        </div>
      </div>

      <div className="bottom-stat">
        <AlertOctagon size={14} className="bottom-icon" style={{ color: 'var(--accent-orange)' }} />
        <div>
          <div className="bottom-label">Under Repair</div>
          <div className="bottom-value">12</div>
        </div>
      </div>

      <div className="bottom-stat">
        <Clock size={14} className="bottom-icon" />
        <div>
          <div className="bottom-label">Avg Response</div>
          <div className="bottom-value">12 min</div>
        </div>
      </div>

      <div className="bottom-stat">
        <Sparkles size={14} className="bottom-icon" style={{ color: 'var(--accent-purple)' }} />
        <div>
          <div className="bottom-label">AI Accuracy</div>
          <div className="bottom-value">92%</div>
        </div>
      </div>

      <div className="bottom-stat">
        <CheckCircle2 size={14} className="bottom-icon" style={{ color: 'var(--accent-cyan)' }} />
        <div>
          <div className="bottom-label">AI Workflow</div>
          <div className="bottom-value" style={{ color: 'var(--accent-cyan)' }}>
            Active ({useMock ? 'Mock' : 'Local'})
          </div>
        </div>
      </div>
    </footer>
  )
}

