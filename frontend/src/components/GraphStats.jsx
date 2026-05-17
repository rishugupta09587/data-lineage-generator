/**
 * components/GraphStats.jsx
 * --------------------------
 * Displays high-level pipeline statistics in a compact metrics bar:
 *   - Node count, edge count, source/sink counts
 *   - Critical path length
 *   - Graph density
 *   - Connectivity indicator
 */

import React from 'react'
import {
  GitBranch, ArrowRight, Database,
  Archive, Activity, Layers, Route
} from 'lucide-react'

const StatPill = ({ icon: Icon, label, value, color = 'text-slate-300' }) => (
  <div className="flex items-center gap-2 bg-surface-800 border border-white/5 rounded-lg px-3 py-2">
    <Icon className={`w-4 h-4 ${color} flex-shrink-0`} />
    <div>
      <p className="text-xs text-slate-500 leading-none mb-0.5">{label}</p>
      <p className={`text-sm font-semibold font-mono ${color}`}>{value}</p>
    </div>
  </div>
)

const GraphStats = ({ stats, dagName }) => {
  if (!stats) return null

  return (
    <div className="flex items-center gap-2 overflow-x-auto pb-1 flex-wrap">
      {dagName && (
        <div className="flex items-center gap-2 bg-indigo-500/15 border border-indigo-500/30
                        rounded-lg px-3 py-2 flex-shrink-0">
          <Layers className="w-4 h-4 text-indigo-400" />
          <p className="text-sm font-semibold text-indigo-300 max-w-[180px] truncate">{dagName}</p>
        </div>
      )}

      <StatPill
        icon={GitBranch}
        label="Nodes"
        value={stats.node_count ?? '—'}
        color="text-slate-200"
      />
      <StatPill
        icon={ArrowRight}
        label="Edges"
        value={stats.edge_count ?? '—'}
        color="text-slate-200"
      />
      <StatPill
        icon={Database}
        label="Sources"
        value={stats.source_count ?? '—'}
        color="text-emerald-400"
      />
      <StatPill
        icon={Archive}
        label="Sinks"
        value={stats.sink_count ?? '—'}
        color="text-rose-400"
      />
      <StatPill
        icon={Route}
        label="Critical Path"
        value={stats.longest_path_length != null ? `${stats.longest_path_length} hops` : '—'}
        color="text-violet-400"
      />
      <StatPill
        icon={Activity}
        label="Density"
        value={stats.density != null ? stats.density.toFixed(3) : '—'}
        color="text-cyan-400"
      />

      {/* Connectivity badge */}
      {stats.is_connected != null && (
        <div className={`flex items-center gap-1.5 rounded-lg px-3 py-2 border text-xs font-medium flex-shrink-0
          ${stats.is_connected
            ? 'bg-emerald-500/10 border-emerald-500/25 text-emerald-400'
            : 'bg-amber-500/10 border-amber-500/25 text-amber-400'
          }`}>
          <div className={`w-1.5 h-1.5 rounded-full ${stats.is_connected ? 'bg-emerald-400' : 'bg-amber-400'}`} />
          {stats.is_connected ? 'Connected' : 'Disconnected'}
        </div>
      )}
    </div>
  )
}

export default GraphStats
