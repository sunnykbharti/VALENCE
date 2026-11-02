import React, { useState, useRef, useEffect } from 'react'
import {
  Plus,
  ArrowUp,
  Sparkles,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Image as ImageIcon,
  X
} from 'lucide-react'
import { useApp } from '../context/AppContext'
import { answerQuestionMock, answerWithImageMock } from '../services/mockBackend'
import { askQuestion, askQuestionWithImage } from '../services/api'

export default function PageQueryAssistant() {
  const {
    chatHistory,
    setChatHistory,
    indexedDocs,
    equipmentModel,
    useMock,
    backendOnline,
    visionImage,
    setVisionImage
  } = useApp()

  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [openDrawers, setOpenDrawers] = useState({})
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)
  const fileInputRef = useRef(null)

  const toggleDrawer = (idx) => {
    setOpenDrawers((prev) => ({ ...prev, [idx]: !prev[idx] }))
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatHistory, loading])

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`
    }
  }, [input])

  const handleSend = async () => {
    if (!input.trim() || loading) return

    const questionText = input.trim()
    const userMsg = {
      role: 'user',
      content: questionText,
      imageName: visionImage ? visionImage.name : null,
    }

    setChatHistory((prev) => [...prev, userMsg])
    setInput('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
    setLoading(true)

    let assistantAns

    if (!useMock && backendOnline) {
      try {
        if (visionImage) {
          assistantAns = await askQuestionWithImage(questionText, visionImage.name, equipmentModel)
        } else {
          assistantAns = await askQuestion(questionText, equipmentModel)
        }
      } catch (err) {
        assistantAns = {
          text: `Backend Error: ${err.message}`,
          evidence: [],
          insufficient_evidence: true,
          observations: [],
        }
      }
    } else {
      assistantAns = visionImage
        ? answerWithImageMock(questionText, visionImage.name, equipmentModel, indexedDocs)
        : answerQuestionMock(questionText, equipmentModel, indexedDocs)
    }

    const assistantMsg = {
      role: 'assistant',
      answer: assistantAns,
      imageName: visionImage ? visionImage.name : null,
    }

    setChatHistory((prev) => [...prev, assistantMsg])
    setLoading(false)
  }

  const handleFileUpload = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const previewUrl = URL.createObjectURL(file)
    setVisionImage({
      name: file.name,
      size: file.size,
      url: previewUrl,
      file,
    })
  }

  const hasMessages = chatHistory.length > 0

  return (
    <div className="gemini-container">
      {/* Hidden file input */}
      <input
        type="file"
        ref={fileInputRef}
        style={{ display: 'none' }}
        accept="image/*"
        onChange={handleFileUpload}
      />

      {/* Main Content Area */}
      <main className="gemini-main-scroll clean-layout">
        {!hasMessages ? (
          /* Empty / Initial State */
          <div className="gemini-hero-view">
            <h1 className="gemini-headline">Where should we start?</h1>

            {/* Attached Image Indicator */}
            {visionImage && (
              <div className="gemini-attached-preview">
                <ImageIcon size={14} />
                <span>{visionImage.name}</span>
                <button
                  type="button"
                  className="gemini-attached-close"
                  onClick={() => setVisionImage(null)}
                >
                  <X size={12} />
                </button>
              </div>
            )}

            {/* Centered Capsule Prompt Bar */}
            <div className="gemini-capsule-bar">
              <button
                type="button"
                className="gemini-capsule-plus"
                title="Attach photo or document"
                onClick={() => fileInputRef.current?.click()}
              >
                <Plus size={18} strokeWidth={2} />
              </button>

              <textarea
                ref={textareaRef}
                className="gemini-capsule-input"
                placeholder="Ask VALENCE"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSend()
                  }
                }}
                rows={1}
              />

              <div className="gemini-capsule-actions">
                {input.trim() && (
                  <button
                    type="button"
                    className="gemini-capsule-send"
                    onClick={handleSend}
                    title="Send"
                  >
                    <ArrowUp size={16} strokeWidth={2.5} />
                  </button>
                )}
              </div>
            </div>
          </div>
        ) : (
          /* Conversation Stream View */
          <div className="gemini-chat-flow">
            {chatHistory.map((msg, idx) => {
              const isUser = msg.role === 'user'

              if (isUser) {
                return (
                  <div key={idx} className="gemini-turn user-turn">
                    {msg.imageName && (
                      <div className="gemini-user-image-tag">
                        <ImageIcon size={13} />
                        <span>{msg.imageName}</span>
                      </div>
                    )}
                    <div className="gemini-user-bubble">{msg.content}</div>
                  </div>
                )
              }

              const ans = msg.answer || {}
              const isDrawerOpen = openDrawers[idx]

              return (
                <div key={idx} className="gemini-turn assistant-turn">
                  <div className="gemini-sparkle-avatar">
                    <svg width="20" height="20" viewBox="0 0 28 28" fill="none">
                      <path
                        d="M14 0C14 7.73199 7.73199 14 0 14C7.73199 14 14 20.268 14 28C14 20.268 20.268 14 28 14C20.268 14 14 7.73199 14 0Z"
                        fill="url(#gemini-turn-sparkle)"
                      />
                      <defs>
                        <linearGradient id="gemini-turn-sparkle" x1="0" y1="0" x2="28" y2="28" gradientUnits="userSpaceOnUse">
                          <stop offset="0%" stopColor="#4E95FF" />
                          <stop offset="50%" stopColor="#9C6BFF" />
                          <stop offset="100%" stopColor="#FFA057" />
                        </linearGradient>
                      </defs>
                    </svg>
                  </div>

                  <div className="gemini-response-content">
                    {ans.insufficient_evidence && (
                      <div className="gemini-insufficient-notice">
                        <AlertTriangle size={15} />
                        <span>Insufficient documentary evidence found in indexed manuals.</span>
                      </div>
                    )}

                    <div className="gemini-response-text">{ans.text}</div>

                    {ans.observations && ans.observations.length > 0 && (
                      <div className="gemini-observations-box">
                        <div className="gemini-obs-header">Visual Observations</div>
                        {ans.observations.map((obs, oIdx) => (
                          <div key={oIdx} className="gemini-obs-item">
                            {obs}
                          </div>
                        ))}
                      </div>
                    )}

                    {ans.evidence && ans.evidence.length > 0 && (
                      <div className="gemini-citations-card">
                        <div
                          className="gemini-citations-toggle"
                          onClick={() => toggleDrawer(idx)}
                        >
                          <span>Sources & Citations ({ans.evidence.length})</span>
                          {isDrawerOpen ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                        </div>

                        {isDrawerOpen && (
                          <div className="gemini-citations-body">
                            {ans.evidence.map((ev, eIdx) => (
                              <div key={eIdx} className="gemini-source-chunk">
                                <div className="gemini-source-meta">
                                  <b>{ev.chunk.filename}</b> • Page {ev.chunk.page} • <code>{ev.source_id}</code>
                                </div>
                                <div className="gemini-source-text">{ev.chunk.text}</div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}

            {loading && (
              <div className="gemini-turn assistant-turn">
                <div className="gemini-sparkle-avatar pulse">
                  <Sparkles size={18} color="#9C6BFF" />
                </div>
                <div className="gemini-thinking-dots">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </main>

      {/* Bottom Sticky Capsule Prompt Bar (When conversation is active) */}
      {hasMessages && (
        <footer className="gemini-bottom-input-wrap">
          {visionImage && (
            <div className="gemini-attached-preview">
              <ImageIcon size={14} />
              <span>{visionImage.name}</span>
              <button
                type="button"
                className="gemini-attached-close"
                onClick={() => setVisionImage(null)}
              >
                <X size={12} />
              </button>
            </div>
          )}

          <div className="gemini-capsule-bar">
            <button
              type="button"
              className="gemini-capsule-plus"
              title="Attach photo or document"
              onClick={() => fileInputRef.current?.click()}
            >
              <Plus size={18} strokeWidth={2} />
            </button>

            <textarea
              ref={textareaRef}
              className="gemini-capsule-input"
              placeholder="Ask VALENCE"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSend()
                }
              }}
              rows={1}
            />

            <div className="gemini-capsule-actions">
              {input.trim() && (
                <button
                  type="button"
                  className="gemini-capsule-send"
                  onClick={handleSend}
                  title="Send"
                >
                  <ArrowUp size={16} strokeWidth={2.5} />
                </button>
              )}
            </div>
          </div>
          <p className="gemini-disclaimer">
            VALENCE strictly verifies technical parameters against indexed manuals
          </p>
        </footer>
      )}
    </div>
  )
}
