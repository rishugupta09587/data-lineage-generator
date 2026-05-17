/**
 * App.jsx
 * --------
 * Root application component.
 * Manages global state:
 *   - Active DAG and its visualization data
 *   - Selected node + lineage highlight
 *   - Left panel mode (upload vs. graph)
 *   - DAG history list
 *
 * Layout:
 *   ┌─────────────────────────────────────────────────────────┐
 *   │  TOPBAR  (logo + search + stats)                        │
 *   ├──────────────┬────────────────────────┬─────────────────┤
 *   │  LEFT PANEL  │   GRAPH CANVAS          │  RIGHT SIDEBAR  │
 *   │  (upload /   │   (Cytoscape.js)        │  (lineage       │
 *   │   history)   │                         │   results)      │
 *   └──────────────┴────────────────────────┴─────────────────┘
 */

import React, { useState, useEffect, useCallback } from 'react'
import { Toaster } from 'react-hot-toast'
import {
  GitBranch, PanelLeft, PanelRight, RefreshCw,
  ChevronLeft, ChevronRight, Info
} from 'lucide-react'
import toast from 'react-hot-toast'

import GraphVisualization from './components/GraphVisualization'
import UploadPanel from './components/UploadPanel'
import Sidebar from './components/Sidebar'
import SearchBar from './components/SearchBar'
import GraphStats from './components/GraphStats'
import VersionPanel from './components/VersionPanel'

import { getDAG, getGraphStats, listDAGs, deleteDAG } from './services/api'

// ─────────────────────────────────────────────────────────────────────────

export default function App() {
  // ── DAG State ───────────────────────────────────────────────────────
  const [currentDagId, setCurrentDagId] = useState(null)
  const [dagData, setDagData] = useState(null)       // { nodes, edges }
  const [dagStats, setDagStats] = useState(null)
  const [dagName, setDagName] = useState(null)
  const [dagHistory, setDagHistory] = useState([])

  // ── Graph Interaction ────────────────────────────────────────────────
  const [selectedNode, setSelectedNode] = useState(null)
  const [highlightData, setHighlightData] = useState(null)

  // ── UI State ─────────────────────────────────────────────────────────
  const [leftPanelOpen, setLeftPanelOpen] = useState(true)
  const [rightPanelOpen, setRightPanelOpen] = useState(true)
  const [loadingDag, setLoadingDag] = useState(false)

  // ── Load DAG history on mount ────────────────────────────────────────
  useEffect(() => {
    refreshHistory()
  }, [])

  const refreshHistory = async () => {
    try {
      const result = await listDAGs()
      setDagHistory(result.dags || [])
    } catch (err) {
      console.error('Failed to load DAG history:', err)
    }
  }

  // ── Load a DAG by ID ─────────────────────────────────────────────────
  const loadDAG = useCallback(async (dagId) => {
    setLoadingDag(true)
    setSelectedNode(null)
    setHighlightData(null)

    try {
      const [dagDetail, statsResult] = await Promise.all([
        getDAG(dagId),
        getGraphStats(dagId),
      ])

      setCurrentDagId(dagId)
      setDagName(dagDetail.name)
      setDagData({
        nodes: dagDetail.nodes,
        edges: dagDetail.edges,
      })
      setDagStats(statsResult)
    } catch (err) {
      toast.error(`Failed to load DAG: ${err.message}`)
    } finally {
      setLoadingDag(false)
    }
  }, [])

  // ── Called after a new DAG is uploaded ───────────────────────────────
  const handleDAGUploaded = useCallback(async (uploadResult) => {
    await refreshHistory()
    await loadDAG(uploadResult.dag_id)
    setRightPanelOpen(false)   // close sidebar — let user explore graph first
  }, [loadDAG])

  // ── Node click from graph canvas ─────────────────────────────────────
  const handleNodeClick = useCallback((nodeId) => {
    setSelectedNode(nodeId)
    setHighlightData(null)           // clear previous highlights on new selection
    if (nodeId) setRightPanelOpen(true)  // auto-open sidebar
  }, [])

  // ── Lineage result from sidebar → highlight graph ────────────────────
  const handleLineageResult = useCallback(({ type, nodes, upstream, downstream, result }) => {
    setHighlightData({ type, nodes, upstream, downstream, result })
  }, [])

  // ── Delete a DAG ─────────────────────────────────────────────────────
  const handleDeleteDAG = useCallback(async (dagId) => {
    try {
      await deleteDAG(dagId)
      toast.success('DAG deleted')
      await refreshHistory()
      if (dagId === currentDagId) {
        setCurrentDagId(null)
        setDagData(null)
        setDagStats(null)
        setDagName(null)
        setSelectedNode(null)
        setHighlightData(null)
      }
    } catch (err) {
      toast.error(err.message)
    }
  }, [currentDagId])

  // ── Node metadata lookup ─────────────────────────────────────────────
  const selectedNodeMeta = selectedNode
    ? dagData?.nodes?.find(n => n.id === selectedNode)
    : null

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-surface-900 text-slate-200">
      {/* Toast notifications */}
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: '#1c2640',
            color: '#e2e8f0',
            border: '1px solid rgba(255,255,255,0.08)',
            fontSize: '13px',
            fontFamily: 'IBM Plex Sans, system-ui',
          },
          success: { iconTheme: { primary: '#10b981', secondary: '#0a0e1a' } },
          error: { iconTheme: { primary: '#f43f5e', secondary: '#0a0e1a' } },
        }}
      />

      {/* ── Top Navigation Bar ─────────────────────────────────────── */}
      <header className="flex items-center gap-4 px-4 py-3 bg-surface-800 border-b border-white/5
                         flex-shrink-0 z-30">
        {/* Logo */}
        <div className="flex items-center gap-2.5 flex-shrink-0">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
            <GitBranch className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold font-display text-white leading-none">
              Data Lineage
            </h1>
            <p className="text-xs text-slate-500 leading-none">Generator</p>
          </div>
        </div>

        <div className="w-px h-6 bg-white/5 flex-shrink-0" />

        {/* Panel toggles */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setLeftPanelOpen(v => !v)}
            className={`p-1.5 rounded-md transition-all ${leftPanelOpen ? 'text-indigo-400 bg-indigo-500/15' : 'text-slate-500 hover:text-slate-300 hover:bg-white/5'}`}
            title="Toggle upload panel"
          >
            <PanelLeft className="w-4 h-4" />
          </button>
          <button
            onClick={() => setRightPanelOpen(v => !v)}
            className={`p-1.5 rounded-md transition-all ${rightPanelOpen ? 'text-indigo-400 bg-indigo-500/15' : 'text-slate-500 hover:text-slate-300 hover:bg-white/5'}`}
            title="Toggle sidebar"
          >
            <PanelRight className="w-4 h-4" />
          </button>
        </div>

        {/* Search — only visible when a DAG is loaded */}
        {dagData && (
          <div className="flex-1 max-w-xs">
            <SearchBar dagData={dagData} onNodeSelect={handleNodeClick} />
          </div>
        )}

        {/* Stats bar */}
        <div className="flex-1 overflow-hidden">
          <GraphStats stats={dagStats} dagName={dagName} />
        </div>

        {/* Reload button */}
        {currentDagId && (
          <button
            onClick={() => loadDAG(currentDagId)}
            disabled={loadingDag}
            className="btn-ghost flex-shrink-0"
            title="Reload DAG"
          >
            <RefreshCw className={`w-4 h-4 ${loadingDag ? 'animate-spin' : ''}`} />
          </button>
        )}

        {/* API docs link */}
        <a
          href="http://localhost:8000/docs"
          target="_blank"
          rel="noreferrer"
          className="btn-ghost flex-shrink-0 text-xs"
        >
          <Info className="w-4 h-4" />
          API Docs
        </a>
      </header>

      {/* ── Main Content Area ──────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">

        {/* Left Panel — Upload & History */}
        {leftPanelOpen && (
          <aside className="w-72 flex-shrink-0 bg-surface-800 border-r border-white/5
                            flex flex-col overflow-hidden animate-slide-in">
            <div className="flex-1 overflow-y-auto p-4">
              <UploadPanel
                onDAGUploaded={handleDAGUploaded}
                dagHistory={dagHistory}
                onSelectDAG={(dagId) => { loadDAG(dagId); setRightPanelOpen(false) }}
                onDeleteDAG={handleDeleteDAG}
              />
            </div>

            {/* Version panel — shows below upload if multiple DAGs exist */}
            {dagHistory.length > 1 && currentDagId && (
              <div className="p-4 border-t border-white/5">
                <VersionPanel
                  dagHistory={dagHistory}
                  currentDagId={currentDagId}
                  onSelectVersion={loadDAG}
                />
              </div>
            )}
          </aside>
        )}

        {/* ── Graph Canvas ────────────────────────────────────────── */}
        <main className="flex-1 relative overflow-hidden">
          {loadingDag && (
            <div className="absolute inset-0 bg-surface-900/80 backdrop-blur-sm z-20
                            flex items-center justify-center">
              <div className="flex flex-col items-center gap-3">
                <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent
                                rounded-full animate-spin" />
                <p className="text-slate-400 text-sm">Loading pipeline graph...</p>
              </div>
            </div>
          )}

          {/* Instructions overlay when no DAG is loaded */}
          {!dagData && !loadingDag && (
            <div className="absolute inset-0 flex items-center justify-center z-10">
              <div className="text-center max-w-sm">
                <div className="w-16 h-16 rounded-2xl bg-surface-700 border border-white/5
                                flex items-center justify-center mx-auto mb-4">
                  <GitBranch className="w-8 h-8 text-indigo-400" />
                </div>
                <h2 className="text-white font-display font-semibold text-lg mb-2">
                  No Pipeline Loaded
                </h2>
                <p className="text-slate-500 text-sm mb-4 leading-relaxed">
                  Upload a DAG JSON file or load a sample pipeline
                  from the left panel to visualize your data lineage.
                </p>
                <div className="grid grid-cols-3 gap-3 text-xs text-slate-600">
                  {[
                    { icon: '⬡', label: 'Source nodes' },
                    { icon: '→', label: 'Data flow edges' },
                    { icon: '◉', label: 'Transformation nodes' },
                  ].map((item) => (
                    <div key={item.label} className="bg-surface-800 rounded-lg p-3 border border-white/5">
                      <div className="text-xl mb-1">{item.icon}</div>
                      <p>{item.label}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          <GraphVisualization
            dagData={dagData}
            selectedNode={selectedNode}
            highlightData={highlightData}
            onNodeClick={handleNodeClick}
            className="w-full h-full"
          />
        </main>

        {/* Right Panel — Lineage Sidebar */}
        {rightPanelOpen && (
          <aside className="w-72 flex-shrink-0 bg-surface-800 border-l border-white/5
                            flex flex-col overflow-hidden animate-slide-in">
            <div className="flex-1 overflow-y-auto p-4">
              <Sidebar
                selectedNode={selectedNode}
                nodeMetadata={selectedNodeMeta}
                currentDagId={currentDagId}
                onLineageResult={handleLineageResult}
                onClose={() => {
                  setSelectedNode(null)
                  setHighlightData(null)
                }}
              />
            </div>
          </aside>
        )}
      </div>
    </div>
  )
}
