import React, { useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { guardianApi } from '@/lib/api'
import RiskGauge from '@/components/RiskGauge'
import ThresholdMeter from '@/components/ThresholdMeter'
import { formatDateTime } from '@/lib/formatDateTime'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts'

type MonitorSummary = {
  last_scan_at?: string | null
  selected_repo?: string | null
  latest_risk_score?: number | null
  latest_risk_level?: string | null
}

type Purchase = {
  purchase_id: string
  repo_full_name: string
  policy_id: string
  policy_name: string
  triggered_risk_score: number
  triggered_risk_level: string
  premium: number
  payout: number
  status: string
  triggered_at: string
}

type RiskLatestResponse = {
  selected_repo?: string | null
  latest_risk?: {
    computed_at: string
    risk_score: number
    risk_level: string
    breakdown: {
      commits_norm: number
      prs_norm: number
      issues_norm: number
      exposure_norm: number
      stability_penalty: number
      activity_score: number
      contributions: Record<string, number>
      explanation: Record<string, any>
    }
  } | null
}

export default function Dashboard() {
  const [windowDays, setWindowDays] = useState(14)
  const [threshold, setThreshold] = useState<number>(70)

  const monitorQuery = useQuery({
    queryKey: ['guardian-monitor-summary'],
    queryFn: async () => {
      const res = await guardianApi.get('/api/guardian/monitor/summary')
      return res.data as MonitorSummary
    },
  })

  const purchasesQuery = useQuery({
    queryKey: ['guardian-purchases'],
    queryFn: async () => {
      const res = await guardianApi.get('/api/guardian/insurance/purchases?limit=5&offset=0')
      return (res.data?.purchases || []) as Purchase[]
    },
  })

  const riskQuery = useQuery({
    queryKey: ['guardian-risk-latest'],
    queryFn: async () => {
      const res = await guardianApi.get('/api/guardian/risk/latest')
      return res.data as RiskLatestResponse
    },
  })

  const scanMutation = useMutation({
    mutationFn: async () => {
      return guardianApi.post('/api/guardian/scan/now', {
        threshold,
        window_days: windowDays,
      })
    },
    onSuccess: async () => {
      toast.success('Scan complete. Risk evaluated.')
      await monitorQuery.refetch()
      await purchasesQuery.refetch()
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || 'Scan failed')
    },
  })

  const selectedRepo = monitorQuery.data?.selected_repo
  const score = monitorQuery.data?.latest_risk_score
  const level = monitorQuery.data?.latest_risk_level
  const hasLatestScore = typeof score === 'number' && Number.isFinite(score)

  const risk = riskQuery.data?.latest_risk
  const normalizedInputData = risk
    ? [
        { name: 'Commits', value: risk.breakdown.commits_norm },
        { name: 'Open PRs', value: risk.breakdown.prs_norm },
        { name: 'Open Issues', value: risk.breakdown.issues_norm },
        { name: 'Exposure', value: risk.breakdown.exposure_norm },
        { name: 'Stability', value: risk.breakdown.stability_penalty },
      ]
    : []

  const contributionsData = risk
    ? Object.entries(risk.breakdown.contributions)
        .map(([name, value]) => ({ name, value }))
        .sort((a, b) => b.value - a.value)
        .slice(0, 8)
    : []

  const riskBadgeClass = useMemo(() => {
    if (!level) return 'badge'
    if (level === 'low') return 'risk-low'
    if (level === 'medium') return 'risk-medium'
    if (level === 'critical') return 'risk-critical'
    return 'risk-high'
  }, [level])

  const riskPillClass = (riskLevel?: string | null) => {
    if (!riskLevel) return 'badge'
    if (riskLevel === 'low') return 'badge risk-low'
    if (riskLevel === 'medium') return 'badge risk-medium'
    if (riskLevel === 'high') return 'badge risk-high'
    if (riskLevel === 'critical') return 'badge risk-critical'
    return 'badge risk-high'
  }

  const riskScoreClass = (riskLevel?: string | null) => {
    if (!riskLevel) return ''
    if (riskLevel === 'critical') return 'text-orange-300'
    if (riskLevel === 'high') return 'text-red-200'
    if (riskLevel === 'medium') return 'text-yellow-200'
    if (riskLevel === 'low') return 'text-green-200'
    return ''
  }

  return (
    <div className="p-6 text-gray-100 min-h-screen bg-gray-950">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-100">Intangible-Asset Monitor</h1>
        <p className="text-gray-300 mt-1">Continuously evaluates repo risk and triggers insurance coverage.</p>
      </div>

      {/* Top 3 panels side-by-side */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="card lg:col-span-3">
          <div className="card-header">
            <div className="text-sm text-gray-300">Selected Repo</div>
            <div className="text-lg font-semibold mt-1">{selectedRepo || '—'}</div>
          </div>
          <div className="card-body">
            <div className="text-sm text-gray-300">Last scan</div>
            <div className="mt-1 font-medium">{formatDateTime(monitorQuery.data?.last_scan_at)}</div>
          </div>
        </div>

        <div className="card lg:col-span-6">
          <div className="card-header">
            <div className="text-sm text-gray-300">Latest Risk</div>
            <div className="mt-3 flex items-center justify-between gap-4">
              <div className={`inline-flex items-center gap-2 badge ${riskBadgeClass}`}>
                <span className="font-semibold">{hasLatestScore ? `${score.toFixed(1)}` : '—'}</span>
                <span className="text-sm">{level ? level.toUpperCase() : ''}</span>
              </div>
              <RiskGauge
                value={hasLatestScore ? score : 0}
                label={hasLatestScore ? 'Overall' : 'No scan yet'}
                valueText={hasLatestScore ? score.toFixed(0) : '—'}
                size={88}
              />
            </div>
          </div>

          <div className="card-body">
            {monitorQuery.isLoading ? (
              <div className="text-gray-300">Loading latest risk...</div>
            ) : hasLatestScore ? (
              <div className="space-y-4">
                <div className="text-gray-200 text-sm">
                  Risk score is computed from commits, open PRs, open issues, and a repository exposure proxy.
                </div>

                {/* Charts (same as RiskScoring page) */}
                {riskQuery.isLoading ? (
                  <div className="text-gray-300 text-sm">Loading charts...</div>
                ) : (
                  <div className="mt-2 grid grid-cols-1 lg:grid-cols-2 gap-4">
                      <div className="bg-gradient-to-b from-primary-900/40 to-gray-950 p-4 rounded-md border border-primary-500/20">
                      <div className="text-sm font-medium mb-2">Normalized Inputs</div>
                      <div className="h-56">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={normalizedInputData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                            <XAxis
                              dataKey="name"
                              tick={{ fill: '#9ca3af', fontSize: 12 }}
                              axisLine={{ stroke: '#334155' }}
                              tickLine={{ stroke: '#334155' }}
                            />
                            <YAxis
                              domain={[0, 'dataMax']}
                              tick={{ fill: '#9ca3af', fontSize: 12 }}
                              axisLine={{ stroke: '#334155' }}
                              tickLine={{ stroke: '#334155' }}
                            />
                            <Tooltip
                              formatter={(v: any) => Number(v).toFixed(3)}
                              contentStyle={{
                                backgroundColor: 'rgba(2, 6, 23, 0.95)',
                                border: '1px solid rgba(148, 163, 184, 0.25)',
                                color: '#e5e7eb',
                              }}
                            />
                            <Bar dataKey="value" fill="#3b82f6" radius={[6, 6, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                      <div className="text-xs text-gray-400 mt-3">Component values used by the MVP risk model.</div>
                    </div>

                    <div className="bg-gradient-to-b from-primary-900/40 to-gray-950 p-4 rounded-md border border-primary-500/20">
                      <div className="text-sm font-medium mb-2">Score Contributions (Top)</div>
                      <div className="h-56">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={contributionsData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                            <XAxis
                              dataKey="name"
                              tick={{ fill: '#9ca3af', fontSize: 12 }}
                              axisLine={{ stroke: '#334155' }}
                              tickLine={{ stroke: '#334155' }}
                            />
                            <YAxis
                              domain={['dataMin', 'dataMax']}
                              tick={{ fill: '#9ca3af', fontSize: 12 }}
                              axisLine={{ stroke: '#334155' }}
                              tickLine={{ stroke: '#334155' }}
                            />
                            <Tooltip
                              formatter={(v: any) => Number(v).toFixed(3)}
                              contentStyle={{
                                backgroundColor: 'rgba(2, 6, 23, 0.95)',
                                border: '1px solid rgba(148, 163, 184, 0.25)',
                                color: '#e5e7eb',
                              }}
                            />
                            <Bar dataKey="value" fill="#f59e0b" radius={[6, 6, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                      <div className="text-xs text-gray-400 mt-3">Showing the strongest contribution terms (top 8).</div>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-3">
                <div className="text-gray-300 text-sm">No scan results yet. Run a scan or set repos in Settings.</div>
                <div className="bg-gradient-to-b from-primary-900/30 to-gray-950 border border-primary-500/20 rounded-md p-4">
                  <ThresholdMeter value={null} threshold={threshold} label="Next: compare score against threshold" />
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="card p-4 lg:col-span-3">
          <div className="font-medium mb-3">Run Scan</div>
          <div className="space-y-3">
            <label className="block">
              <div className="text-sm text-gray-200 mb-1">Risk Threshold</div>
              <input
                type="number"
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
                className="w-full border-gray-800 border rounded-md px-3 py-2 bg-gray-950/30 text-gray-100"
              />
            </label>
            <label className="block">
              <div className="text-sm text-gray-200 mb-1">Window Days</div>
              <input
                type="number"
                value={windowDays}
                onChange={(e) => setWindowDays(Number(e.target.value))}
                className="w-full border-gray-800 border rounded-md px-3 py-2 bg-gray-950/30 text-gray-100"
              />
            </label>

            <button
              className="btn btn-primary w-full"
              onClick={() => scanMutation.mutate()}
              disabled={scanMutation.isPending}
            >
              {scanMutation.isPending ? 'Scanning...' : 'Scan Now'}
            </button>
          </div>
        </div>
      </div>

      <div className="card mt-6">
        <div className="card-header">
          <div className="flex items-center justify-between w-full">
            <div>
              <div className="text-sm text-gray-300">Recent Insurance Purchases</div>
              <div className="text-lg font-semibold mt-1">Triggered Coverage</div>
            </div>
            <div className="text-sm text-gray-500">
              {purchasesQuery.data ? `${purchasesQuery.data.length} latest` : ''}
            </div>
          </div>
        </div>

            <div className="card-body">
          {purchasesQuery.isLoading ? (
            <div className="text-gray-300">Loading purchases...</div>
          ) : purchasesQuery.data && purchasesQuery.data.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-200 bg-primary-500/10">
                    <th className="py-2">Repo</th>
                    <th className="py-2">Policy</th>
                    <th className="py-2">Risk</th>
                    <th className="py-2">Triggered</th>
                  </tr>
                </thead>
                <tbody>
                  {purchasesQuery.data.map((p) => (
                    <tr key={p.purchase_id} className="border-t border-gray-100 hover:bg-primary-50/30 transition-colors">
                      <td className="py-2 font-medium">{p.repo_full_name}</td>
                      <td className="py-2">{p.policy_name}</td>
                      <td className="py-2">
                        <span className={riskScoreClass(p.triggered_risk_level)}>
                          {p.triggered_risk_score.toFixed(1)}
                        </span>{' '}
                        <span className={riskPillClass(p.triggered_risk_level)}>
                          {String(p.triggered_risk_level).toUpperCase()}
                        </span>
                      </td>
                      <td className="py-2 text-gray-300">{formatDateTime(p.triggered_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-gray-300 text-sm">No purchases yet. Crossing your threshold triggers simulated policies.</div>
          )}
        </div>
      </div>
    </div>
  )
}

