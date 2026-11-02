import React from 'react'
import { Users, BarChart2, Package, Activity, AlertTriangle } from 'lucide-react'
import { useApp } from '../context/AppContext'

export default function PageOverview() {
  const { indexedDocs, chatHistory, useMock } = useApp()

  const docCount = Object.keys(indexedDocs).length
  const userQueries = chatHistory.filter((m) => m.role === 'user')
  const assistantAnswers = chatHistory.filter((m) => m.role === 'assistant')
  const insufficientCount = assistantAnswers.filter((m) => m.answer?.insufficient_evidence).length
  const answeredCount = assistantAnswers.length - insufficientCount

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {useMock && (
        <div style={{
          background: 'rgba(251, 146, 60, 0.1)',
          borderLeft: '4px solid var(--accent-orange)',
          padding: '10px 16px',
          borderRadius: '8px',
          color: 'var(--accent-orange)',
          fontSize: '0.82rem',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <AlertTriangle size={16} />
          <span><b>MOCK BACKEND MODE:</b> Vector retrieval, LLM synthesis, and vision profiles are simulated locally.</span>
        </div>
      )}

      <div>
        <div className="section-header">
          <Users size={18} style={{ color: 'var(--accent-cyan)' }} />
          <span>Technician Activity Center</span>
        </div>

        <div className="grid-2">
          <div className="tech-card">
            <div className="tech-header">
              <div className="tech-avatar">👨‍🔧</div>
              <div>
                <div className="tech-name">David Wilson</div>
                <div className="tech-role">Senior Maintenance Engineer</div>
              </div>
              <div className="tech-actions">
                <span className="pill pill-green">On Site</span>
              </div>
            </div>

            <div>
              <div className="tech-task-label">Current Task</div>
              <div className="tech-task-name">Inspecting Conveyor Unit C14</div>
            </div>

            <div className="tech-stats">
              <div>
                <div className="tech-stat-label">Response Time</div>
                <div className="tech-stat-value" style={{ color: 'var(--accent-cyan)' }}>12 Minutes</div>
              </div>
              <div>
                <div className="tech-stat-label">Efficiency Score</div>
                <div className="tech-stat-value" style={{ color: 'var(--accent-green)' }}>96%</div>
              </div>
            </div>
          </div>

          <div className="tech-card">
            <div className="tech-header">
              <div className="tech-avatar" style={{ background: 'linear-gradient(135deg, #3b1d54, #1b122c)' }}>👩‍🔧</div>
              <div>
                <div className="tech-name">Sophia Miller</div>
                <div className="tech-role">Electrical Systems Specialist</div>
              </div>
              <div className="tech-actions">
                <button className="btn btn-outline">Reassign</button>
                <button className="btn btn-primary">Contact</button>
              </div>
            </div>

            <div>
              <div className="tech-task-label">Current Task</div>
              <div className="tech-task-name">Repairing Compressor Unit CC9</div>
              <div style={{ fontSize: '0.72rem', color: 'var(--accent-orange)', marginTop: '2px' }}>
                Waiting for spare components
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                <span>Shift Progress</span>
                <span style={{ color: 'var(--accent-green)', fontWeight: 600 }}>74% Shift Done</span>
              </div>
              <div className="progress-bar-track">
                <div className="progress-bar-fill" style={{ width: '74%' }} />
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid-3">
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <div style={{ fontWeight: 600, fontSize: '0.88rem' }}>Maintenance Productivity</div>
            <BarChart2 size={16} color="var(--text-muted)" />
          </div>

          <div style={{ height: '110px', display: 'flex', alignItems: 'flex-end', gap: '8px', paddingBottom: '10px' }}>
            {[40, 65, 30, 85, 95, 75].map((val, idx) => (
              <div key={idx} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%', justifyContent: 'flex-end' }}>
                <div
                  style={{
                    width: '100%',
                    height: `${val}%`,
                    background: idx >= 3 ? 'var(--accent-green)' : 'linear-gradient(180deg, #818cf8, #4f46e5)',
                    borderRadius: '4px 4px 0 0',
                  }}
                />
              </div>
            ))}
          </div>

          <div style={{ marginTop: '12px', borderTop: '1px solid var(--border)', paddingTop: '10px' }}>
            <div className="insight-row">
              <span className="insight-label">Avg Resolution Time</span>
              <span className="insight-value" style={{ color: 'var(--accent-cyan)' }}>1.8 Hours</span>
            </div>
            <div className="insight-row">
              <span className="insight-label">Completed Repairs</span>
              <span className="insight-value">342</span>
            </div>
            <div className="insight-row">
              <span className="insight-label">Emergency Response</span>
              <span className="insight-value" style={{ color: 'var(--accent-green)' }}>98.5%</span>
            </div>
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <div style={{ fontWeight: 600, fontSize: '0.88rem' }}>Live Work Order Flow</div>
            <Activity size={16} color="var(--text-muted)" />
          </div>

          <div className="kanban">
            <div>
              <div className="kanban-col-header">
                <span>NEW</span>
                <span className="kanban-badge">(12)</span>
              </div>
              <div className="wo-card">
                <div>WO-48321</div>
                <div className="wo-bar"><div className="wo-bar-fill" style={{ width: '20%', background: 'var(--text-muted)' }} /></div>
              </div>
              <div className="wo-card">
                <div>WO-48322</div>
                <div className="wo-bar"><div className="wo-bar-fill" style={{ width: '15%', background: 'var(--text-muted)' }} /></div>
              </div>
            </div>

            <div>
              <div className="kanban-col-header">
                <span>ASSIGNED</span>
                <span className="kanban-badge">(8)</span>
              </div>
              <div className="wo-card">
                <div>WO-48310</div>
                <div className="wo-bar"><div className="wo-bar-fill" style={{ width: '45%', background: 'var(--accent-orange)' }} /></div>
              </div>
            </div>

            <div>
              <div className="kanban-col-header">
                <span style={{ color: 'var(--accent-cyan)' }}>IN PROG</span>
                <span className="kanban-badge active">(4)</span>
              </div>
              <div className="wo-card" style={{ borderColor: 'var(--accent-cyan)', background: 'rgba(34,211,238,0.05)' }}>
                <div style={{ color: 'var(--accent-cyan)' }}>WO-48291</div>
                <div className="wo-bar"><div className="wo-bar-fill" style={{ width: '80%', background: 'var(--accent-cyan)' }} /></div>
              </div>
              <div className="wo-card">
                <div>WO-48302</div>
                <div className="wo-bar"><div className="wo-bar-fill" style={{ width: '60%', background: 'var(--accent-cyan)' }} /></div>
              </div>
            </div>

            <div>
              <div className="kanban-col-header">
                <span>VERIFY</span>
                <span className="kanban-badge">(2)</span>
              </div>
              <div className="wo-card">
                <div>WO-48280</div>
                <div className="wo-bar"><div className="wo-bar-fill" style={{ width: '100%', background: 'var(--accent-green)' }} /></div>
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <div style={{ fontWeight: 600, fontSize: '0.88rem' }}>Inventory & Spare Parts</div>
            <Package size={16} color="var(--text-muted)" />
          </div>

          <div className="inv-item">
            <div className="inv-icon warn">⚠️</div>
            <div>
              <div className="inv-name">Bearing Sets (H-Series)</div>
              <div className="inv-sub">Low Stock Alert • 2 Remaining</div>
            </div>
            <button className="inv-order-btn">Order</button>
          </div>

          <div className="inv-item">
            <div className="inv-icon ok">📦</div>
            <div>
              <div className="inv-name">Cooling Fan Assy</div>
              <div className="inv-sub ok-text">14 in Stock</div>
            </div>
          </div>

          <div className="inv-item">
            <div className="inv-icon info">🔄</div>
            <div>
              <div className="inv-name">Hydraulic Filters</div>
              <div className="inv-sub info-text">Arriving Tomorrow (50 units)</div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid-4">
        <div className="kpi-card">
          <div className="kpi-label">Indexed Documents</div>
          <div className="kpi-value">{docCount}</div>
          <div className="kpi-sub">Available SOPs in DB</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Total Q&A Queries</div>
          <div className="kpi-value">{userQueries.length}</div>
          <div className="kpi-sub">Queries executed</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Substantiated Answers</div>
          <div className="kpi-value" style={{ color: 'var(--accent-green)' }}>{answeredCount}</div>
          <div className="kpi-sub">Supported by evidence</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Insufficient Evidence</div>
          <div className="kpi-value" style={{ color: insufficientCount > 0 ? 'var(--accent-orange)' : 'var(--text-muted)' }}>
            {insufficientCount}
          </div>
          <div className="kpi-sub">Safely flagged no hallucination</div>
        </div>
      </div>
    </div>
  )
}

