/**
 * components/VersionPanel.jsx
 * ----------------------------
 * Displays the version history of a loaded DAG.
 * Simulates the "Versioned DAG" advanced feature —
 * each upload of a DAG gets a new version record.
 * Users can switch between DAG versions to compare lineage.
 */

import React from 'react'
import { Clock, CheckCircle, GitCommit } from 'lucide-react'

const VersionPanel = ({ dagHistory, currentDagId, onSelectVersion }) => {
  if (!dagHistory || dagHistory.length < 2) return null

  const formatDate = (isoStr) => {
    if (!isoStr) return '—'
    return new Date(isoStr).toLocaleString('en-IN', {
      day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
    })
  }

  return (
    <div className="glass-panel p-4">
      <div className="flex items-center gap-2 mb-3">
        <GitCommit className="w-4 h-4 text-violet-400" />
        <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-widest">
          DAG Versions
        </h3>
      </div>

      <div className="flex flex-col gap-1.5 max-h-48 overflow-y-auto">
        {dagHistory.map((dag, idx) => {
          const isCurrent = dag.dag_id === currentDagId
          return (
            <button
              key={dag.dag_id}
              onClick={() => onSelectVersion(dag.dag_id)}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-all border
                ${isCurrent
                  ? 'bg-violet-500/15 border-violet-500/30 text-violet-300'
                  : 'bg-surface-700 border-white/5 text-slate-400 hover:border-white/10 hover:text-slate-200'
                }`}
            >
              {isCurrent
                ? <CheckCircle className="w-3.5 h-3.5 text-violet-400 flex-shrink-0" />
                : <Clock className="w-3.5 h-3.5 text-slate-600 flex-shrink-0" />
              }
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium truncate">
                  {dag.name}
                  <span className="text-slate-500 font-normal ml-1">v{dag.version}</span>
                </p>
                <p className="text-xs text-slate-600 font-mono">
                  {dag.node_count}n · {dag.edge_count}e
                </p>
              </div>
              {isCurrent && (
                <span className="text-xs bg-violet-500/20 text-violet-400 px-1.5 py-0.5 rounded flex-shrink-0">
                  active
                </span>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}

export default VersionPanel
