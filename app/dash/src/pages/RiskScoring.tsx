import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { guardianApi } from '@/lib/api'
import RiskGauge from '@/components/RiskGauge'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts'
import { formatDateTime } from '@/lib/formatDateTime'

type RiskLatestResponse = {
  last_scan_at?: string | null
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

export default function RiskScoring() {
  const riskQuery = useQuery({
    queryKey: ['guardian-risk-latest'],
    queryFn: async () => {
      const res = await guardianApi.get('/api/guardian/risk/latest')
      return res.data as RiskLatestResponse
    },
  })

  const risk = riskQuery.data?.latest_risk

  const riskClassFor = (riskLevel?: string) => {
    if (!riskLevel) return 'badge'
    if (riskLevel === 'low') return 'badge risk-low'
    if (riskLevel === 'medium') return 'badge risk-medium'
    if (riskLevel === 'high') return 'badge risk-high'
    if (riskLevel === 'critical') return 'badge risk-critical'
    return 'badge risk-high'
  }

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

  return (
    <div className="p-6 min-h-screen bg-gray-950 text-gray-100">
      <h1 className="text-2xl font-semibold">Risk Scoring</h1>
      <p className="text-gray-300 mt-1">Explainable scoring based on repo activity and exposure proxy.</p>

        <div className="card mt-6">
        <div className="card-header">
            <div className="text-sm text-gray-300">Selected Repo</div>
          <div className="text-lg font-semibold mt-1">{riskQuery.data?.selected_repo || '—'}</div>
        </div>
        <div className="card-body">
          {riskQuery.isLoading ? (
              <div className="text-gray-300">Loading risk score...</div>
          ) : risk ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between gap-4">
                  <div className="text-sm text-gray-300">Latest Risk</div>
                  <div className={riskClassFor(risk.risk_level as any)}>{risk.risk_level.toUpperCase()}</div>
              </div>

              <div className="mt-1 flex items-center justify-between gap-4">
                <RiskGauge value={risk.risk_score} label="Overall" size={110} />
                <div className="flex-1">
                  <div className="text-4xl font-semibold leading-tight">{risk.risk_score.toFixed(1)}</div>
                      <div className="text-xs text-gray-400 mt-2">
                    computed_at: {formatDateTime(risk.computed_at)}
                  </div>
                </div>
              </div>

              <div className="mt-2 grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <div className="bg-gray-950/40 p-4 rounded-md border border-gray-800">
                      <div className="text-sm font-medium mb-2 text-gray-100">Normalized Inputs</div>
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

                    <div className="bg-gray-950/40 p-4 rounded-md border border-gray-800">
                      <div className="text-sm font-medium mb-2 text-gray-100">Score Contributions (Top)</div>
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

              <div className="bg-gray-950/40 border border-gray-800 rounded-md p-4">
                <div className="text-sm font-medium mb-2 text-gray-100">Explanation</div>
                <pre className="text-xs whitespace-pre-wrap text-gray-100">
                  {JSON.stringify(risk.breakdown.explanation, null, 2)}
                </pre>
              </div>
            </div>
          ) : (
            <div className="text-gray-300 text-sm">No scan results yet. Use Settings to select repos and run a scan.</div>
          )}
        </div>
      </div>
    </div>
  )
}

