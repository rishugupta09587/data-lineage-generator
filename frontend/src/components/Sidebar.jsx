/**
 * components/Sidebar.jsx
 * -----------------------
 * Right-side panel that shows:
 *   - Selected node metadata
 *   - Lineage query controls (upstream / downstream / full / impact)
 *   - Lineage results (node list, paths, impact score)
 *   - Export buttons
 */

import React, { useState } from 'react'
import {
  ArrowUpCircle, ArrowDownCircle, GitBranch, Zap,
  Download, ChevronDown, ChevronRight, AlertTriangle,
  CheckCircle, Database, Cog, Archive, X
} from 'lucide-react'
import toast from 'react-hot-toast'
import {
  getUpstream, getDownstream, getFullLineage,
  getImpactAnalysis, getExportUrl
} from '../services/api'
import clsx from 'clsx'

// ── Node type icons and colors ────────────────────────────────────────────
const NodeTypeIcon = ({ type }) => {
  const icons = {
    source: <Database className="w-3.5 h-3.5 text-emerald-400" />,
    transformation: <Cog className="w-3.5 h-3.5 text-indigo-400" />,
    sink: <Archive className="w-3.5 h-3.5 text-rose-400" />,
  }
  return icons[type] || icons.transformation
}

const RISK_COLORS = {
  CRITICAL: 'badge-critical',
  HIGH: 'badge-high',
  MEDIUM: 'badge-medium',
  LOW: 'badge-low',
}

// ── Collapsible Section ───────────────────────────────────────────────────
const Section = ({ title, count, children, defaultOpen = true }) => {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border border-white/5 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-2.5 bg-surface-700
                   hover:bg-surface-600 transition-colors text-left"
      >
        <span className="text-xs font-semibold text-slate-300">{title}</span>
        <div className="flex items-center gap-2">
          {count !== undefined && (
            <span className="bg-indigo-500/20 text-indigo-400 text-xs px-1.5 py-0.5 rounded font-mono">
              {count}
            </span>
          )}
          {open
            ? <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
            : <ChevronRight className="w-3.5 h-3.5 text-slate-500" />
          }
        </div>
      </button>
      {open && <div className="p-3 bg-surface-800">{children}</div>}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────

const Sidebar = ({
  selectedNode,
  nodeMetadata,
  currentDagId,
  onLineageResult,
  onClose,
}) => {
  const [activeQuery, setActiveQuery] = useState(null)
  const [lineageResult, setLineageResult] = useState(null)
  const [impactResult, setImpactResult] = useState(null)
  const [loading, setLoading] = useState(false)

  if (!selectedNode) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center px-4">
        <div className="w-12 h-12 rounded-xl bg-surface-700 flex items-center justify-center mb-3">
          <GitBranch className="w-6 h-6 text-slate-500" />
        </div>
        <p className="text-slate-400 text-sm font-medium">No node selected</p>
        <p className="text-slate-600 text-xs mt-1">Click a node in the graph to explore its lineage</p>
      </div>
    )
  }

  // ── Query handlers ──────────────────────────────────────────────────
  const runQuery = async (type) => {
    if (!currentDagId || !selectedNode) return
    setLoading(true)
    setActiveQuery(type)
    setLineageResult(null)
    setImpactResult(null)

    try {
      let result
      if (type === 'upstream') result = await getUpstream(currentDagId, selectedNode)
      else if (type === 'downstream') result = await getDownstream(currentDagId, selectedNode)
      else if (type === 'full') result = await getFullLineage(currentDagId, selectedNode)
      else if (type === 'impact') result = await getImpactAnalysis(currentDagId, selectedNode)

      if (type === 'impact') {
        setImpactResult(result)
        // Build highlight set from impact
        const highlightSet = new Set([
          selectedNode,
          ...(result.directly_affected || []),
          ...(result.transitively_affected || []),
        ])
        onLineageResult({
          type: 'impact',
          nodes: highlightSet,
          result,
        })
      } else {
        setLineageResult(result)
        const highlightSet = new Set(result.nodes?.map(n => n.id) || [])
        onLineageResult({ type, nodes: highlightSet, result })
      }

      toast.success(`${type} lineage computed (${result.node_count || result.transitively_affected?.length} nodes)`, {
        icon: type === 'impact' ? '⚡' : '🔍',
      })
    } catch (err) {
      toast.error(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleExport = (format) => {
    const url = getExportUrl(currentDagId, selectedNode, format, activeQuery || 'full')
    window.open(url, '_blank')
  }

  const typeBadgeClass = {
    source: 'badge-source',
    transformation: 'badge-transform',
    sink: 'badge-sink',
  }[nodeMetadata?.type] || 'badge'

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-start justify-between mb-4 flex-shrink-0">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <NodeTypeIcon type={nodeMetadata?.type} />
            <h3 className="text-white font-semibold text-sm font-display truncate">
              {nodeMetadata?.name || selectedNode}
            </h3>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className={typeBadgeClass}>
              {nodeMetadata?.type || 'unknown'}
            </span>
            {nodeMetadata?.operation && (
              <span className="badge bg-surface-600 text-slate-300 border border-white/10">
                {nodeMetadata.operation}
              </span>
            )}
            {nodeMetadata?.version && (
              <span className="badge bg-surface-600 text-slate-400 border border-white/5">
                v{nodeMetadata.version}
              </span>
            )}
          </div>
        </div>
        {onClose && (
          <button onClick={onClose} className="p-1 hover:bg-white/5 rounded text-slate-500 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Node ID */}
      <div className="bg-surface-900 border border-white/5 rounded-lg px-3 py-2 mb-4 flex-shrink-0">
        <p className="text-slate-600 text-xs mb-0.5">Node ID</p>
        <code className="text-indigo-400 text-xs font-mono">{selectedNode}</code>
      </div>

      {/* Description */}
      {nodeMetadata?.description && (
        <p className="text-slate-400 text-xs mb-4 flex-shrink-0">{nodeMetadata.description}</p>
      )}

      {/* Lineage Query Buttons */}
      <div className="flex-shrink-0 mb-4">
        <p className="section-title">Lineage Analysis</p>
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => runQuery('upstream')}
            disabled={loading}
            className={clsx(
              'flex items-center gap-1.5 px-2 py-2 rounded-lg text-xs font-medium transition-all border',
              activeQuery === 'upstream'
                ? 'bg-blue-500/20 border-blue-500/50 text-blue-300'
                : 'bg-surface-700 border-white/5 text-slate-300 hover:border-blue-500/30 hover:text-blue-300'
            )}
          >
            <ArrowUpCircle className="w-3.5 h-3.5" />
            Upstream
          </button>
          <button
            onClick={() => runQuery('downstream')}
            disabled={loading}
            className={clsx(
              'flex items-center gap-1.5 px-2 py-2 rounded-lg text-xs font-medium transition-all border',
              activeQuery === 'downstream'
                ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300'
                : 'bg-surface-700 border-white/5 text-slate-300 hover:border-emerald-500/30 hover:text-emerald-300'
            )}
          >
            <ArrowDownCircle className="w-3.5 h-3.5" />
            Downstream
          </button>
          <button
            onClick={() => runQuery('full')}
            disabled={loading}
            className={clsx(
              'flex items-center gap-1.5 px-2 py-2 rounded-lg text-xs font-medium transition-all border',
              activeQuery === 'full'
                ? 'bg-violet-500/20 border-violet-500/50 text-violet-300'
                : 'bg-surface-700 border-white/5 text-slate-300 hover:border-violet-500/30 hover:text-violet-300'
            )}
          >
            <GitBranch className="w-3.5 h-3.5" />
            Full Lineage
          </button>
          <button
            onClick={() => runQuery('impact')}
            disabled={loading}
            className={clsx(
              'flex items-center gap-1.5 px-2 py-2 rounded-lg text-xs font-medium transition-all border',
              activeQuery === 'impact'
                ? 'bg-amber-500/20 border-amber-500/50 text-amber-300'
                : 'bg-surface-700 border-white/5 text-slate-300 hover:border-amber-500/30 hover:text-amber-300'
            )}
          >
            <Zap className="w-3.5 h-3.5" />
            Impact
          </button>
        </div>
        {loading && (
          <div className="mt-2 flex items-center gap-2 text-xs text-slate-500">
            <div className="w-3 h-3 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            Computing lineage...
          </div>
        )}
      </div>

      {/* Scrollable Results Area */}
      <div className="flex-1 overflow-y-auto flex flex-col gap-3 min-h-0">

        {/* Impact Analysis Results */}
        {impactResult && activeQuery === 'impact' && (
          <>
            <div className={clsx(
              'rounded-xl p-4 border',
              impactResult.risk_level === 'CRITICAL' ? 'bg-red-500/10 border-red-500/30' :
              impactResult.risk_level === 'HIGH' ? 'bg-orange-500/10 border-orange-500/30' :
              impactResult.risk_level === 'MEDIUM' ? 'bg-amber-500/10 border-amber-500/30' :
              'bg-green-500/10 border-green-500/30'
            )}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  <span className="text-sm font-semibold text-white">Impact Analysis</span>
                </div>
                <span className={RISK_COLORS[impactResult.risk_level]}>
                  {impactResult.risk_level}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-3 mt-3">
                <div>
                  <p className="text-xs text-slate-500">Impact Score</p>
                  <p className="text-xl font-bold text-white font-mono">
                    {(impactResult.impact_score * 100).toFixed(0)}%
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Affected Nodes</p>
                  <p className="text-xl font-bold text-white font-mono">
                    {impactResult.transitively_affected?.length || 0}
                  </p>
                </div>
              </div>
            </div>

            <Section title="Directly Affected" count={impactResult.directly_affected?.length || 0}>
              {impactResult.directly_affected?.length === 0
                ? <p className="text-slate-500 text-xs">No directly affected nodes</p>
                : impactResult.directly_affected?.map(nodeId => (
                    <div key={nodeId} className="flex items-center gap-2 py-1">
                      <div className="w-1.5 h-1.5 rounded-full bg-amber-500 flex-shrink-0" />
                      <code className="text-xs text-slate-300 font-mono">{nodeId}</code>
                    </div>
                  ))
              }
            </Section>

            {impactResult.transitively_affected?.length > 0 && (
              <Section title="All Affected Nodes" count={impactResult.transitively_affected.length} defaultOpen={false}>
                {impactResult.transitively_affected?.map(nodeId => (
                  <div key={nodeId} className="flex items-center gap-2 py-1">
                    <div className="w-1.5 h-1.5 rounded-full bg-orange-500/60 flex-shrink-0" />
                    <code className="text-xs text-slate-400 font-mono">{nodeId}</code>
                  </div>
                ))}
              </Section>
            )}
          </>
        )}

        {/* Lineage Results */}
        {lineageResult && activeQuery !== 'impact' && (
          <>
            <div className="bg-surface-700/50 border border-white/5 rounded-lg p-3">
              <div className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <p className="text-lg font-bold text-white font-mono">{lineageResult.node_count}</p>
                  <p className="text-xs text-slate-500">Nodes</p>
                </div>
                <div>
                  <p className="text-lg font-bold text-white font-mono">{lineageResult.edges?.length || 0}</p>
                  <p className="text-xs text-slate-500">Edges</p>
                </div>
                <div>
                  <p className="text-lg font-bold text-white font-mono">{lineageResult.depth}</p>
                  <p className="text-xs text-slate-500">Depth</p>
                </div>
              </div>
              {lineageResult.from_cache && (
                <div className="flex items-center gap-1 mt-2 text-xs text-emerald-400">
                  <CheckCircle className="w-3 h-3" />
                  Served from cache
                </div>
              )}
            </div>

            <Section title="Nodes in Lineage" count={lineageResult.node_count}>
              {lineageResult.nodes?.map(node => (
                <div key={node.id} className="flex items-center gap-2 py-1.5 border-b border-white/5 last:border-0">
                  <NodeTypeIcon type={node.type} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-slate-200 font-medium truncate">{node.name}</p>
                    <code className="text-xs text-slate-500 font-mono">{node.id}</code>
                  </div>
                </div>
              ))}
            </Section>

            {lineageResult.paths?.length > 0 && (
              <Section title="Lineage Paths" count={lineageResult.paths.length} defaultOpen={false}>
                {lineageResult.paths.slice(0, 10).map((pathObj, idx) => (
                  <div key={idx} className="mb-2 last:mb-0">
                    <p className="text-xs text-slate-500 mb-1">Path {idx + 1} ({pathObj.length} hops)</p>
                    <div className="flex items-center flex-wrap gap-1">
                      {pathObj.path.map((nodeId, i) => (
                        <React.Fragment key={i}>
                          <code className="text-xs text-indigo-300 font-mono bg-indigo-500/10 px-1.5 py-0.5 rounded">
                            {nodeId}
                          </code>
                          {i < pathObj.path.length - 1 && (
                            <span className="text-slate-600 text-xs">→</span>
                          )}
                        </React.Fragment>
                      ))}
                    </div>
                  </div>
                ))}
                {lineageResult.paths.length > 10 && (
                  <p className="text-slate-500 text-xs">+{lineageResult.paths.length - 10} more paths</p>
                )}
              </Section>
            )}
          </>
        )}

        {/* Schema / Column Lineage */}
        {nodeMetadata?.schema_info && (
          <Section title="Column Schema" defaultOpen={false}>
            {Object.entries(nodeMetadata.schema_info).map(([col, info]) => (
              <div key={col} className="py-1.5 border-b border-white/5 last:border-0">
                <div className="flex items-center justify-between">
                  <code className="text-xs text-cyan-400 font-mono">{col}</code>
                  <span className="text-xs text-slate-500">{info.type}</span>
                </div>
                {info.description && (
                  <p className="text-xs text-slate-600 mt-0.5">{info.description}</p>
                )}
              </div>
            ))}
          </Section>
        )}
      </div>

      {/* Export Buttons */}
      {(lineageResult || impactResult) && (
        <div className="flex-shrink-0 pt-3 border-t border-white/5 mt-3">
          <p className="section-title">Export Report</p>
          <div className="flex gap-2">
            <button
              onClick={() => handleExport('json')}
              className="btn-ghost flex-1 justify-center text-xs"
            >
              <Download className="w-3.5 h-3.5" />
              JSON
            </button>
            <button
              onClick={() => handleExport('pdf')}
              className="btn-ghost flex-1 justify-center text-xs"
            >
              <Download className="w-3.5 h-3.5" />
              PDF
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default Sidebar
