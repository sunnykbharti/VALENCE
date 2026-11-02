import { useState, useEffect } from 'react'
import Sidebar from './components/Sidebar'
import Topbar from './components/Topbar'
import BottomBar from './components/BottomBar'
import PageOverview from './pages/PageOverview'
import PageQueryAssistant from './pages/PageQueryAssistant'
import PageImageAnalysis from './pages/PageImageAnalysis'
import PageDocumentLibrary from './pages/PageDocumentLibrary'
import PageSettings from './pages/PageSettings'
import { AppContext } from './context/AppContext'
import { checkBackendHealth, fetchIndexedDocuments } from './services/api'
import './index.css'

const PAGES = ['Overview', 'Query Assistant', 'Image Analysis', 'Document Library', 'Settings']

export default function App() {
  const [activePage, setActivePage] = useState('Overview')
  const [useMock, setUseMock] = useState(true)
  const [backendOnline, setBackendOnline] = useState(false)
  const [chatHistory, setChatHistory] = useState([])
  const [indexedDocs, setIndexedDocs] = useState({})
  const [lastSummary, setLastSummary] = useState(null)
  const [visionImage, setVisionImage] = useState(null)
  const [equipmentModel, setEquipmentModel] = useState('')

  // Poll backend health and sync documents
  useEffect(() => {
    checkBackendHealth().then((health) => {
      if (health && health.status === 'healthy') {
        setBackendOnline(true)
        fetchIndexedDocuments().then((res) => {
          const docs = res.documents || {}
          const chunksByDoc = res.chunks || {}
          if (docs && Object.keys(docs).length > 0) {
            const formatted = {}
            Object.entries(docs).forEach(([fname, meta]) => {
              formatted[fname] = {
                ...meta,
                chunks: chunksByDoc[fname] || [],
              }
            })
            setIndexedDocs(formatted)
          }
        })
      } else {
        setBackendOnline(false)
      }
    })
  }, [])

  const ctx = {
    useMock, setUseMock,
    backendOnline,
    chatHistory, setChatHistory,
    indexedDocs, setIndexedDocs,
    lastSummary, setLastSummary,
    visionImage, setVisionImage,
    equipmentModel, setEquipmentModel,
  }

  const renderPage = () => {
    switch (activePage) {
      case 'Overview':         return <PageOverview />
      case 'Query Assistant':  return <PageQueryAssistant />
      case 'Image Analysis':   return <PageImageAnalysis />
      case 'Document Library': return <PageDocumentLibrary />
      case 'Settings':         return <PageSettings />
      default:                 return <PageOverview />
    }
  }

  return (
    <AppContext.Provider value={ctx}>
      <div className="shell">
        <Sidebar
          pages={PAGES}
          activePage={activePage}
          setActivePage={setActivePage}
          useMock={useMock}
          setUseMock={setUseMock}
          backendOnline={backendOnline}
        />
        <div className="main">
          <Topbar activePage={activePage} equipmentModel={equipmentModel} setEquipmentModel={setEquipmentModel} />
          <div className="content">
            <div className="page">{renderPage()}</div>
          </div>
          <BottomBar indexedDocs={indexedDocs} chatHistory={chatHistory} useMock={useMock} />
        </div>
      </div>
    </AppContext.Provider>
  )
}

