import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { guardianApi } from '@/lib/api'

type RiskLatestResponse = {
  selected_repo?: string | null
  latest_risk?: {
    risk_score: number
    risk_level: string
    computed_at: string
    breakdown: any
  } | null
}

export default function Assets() {
  const latestQuery = useQuery({
    queryKey: ['guardian-risk-latest-short'],
    queryFn: async () => {
      const res = await guardianApi.get('/api/guardian/risk/latest')
      return res.data as RiskLatestResponse
    },
  })

  return (
    <div className="p-6 min-h-screen bg-gray-950 text-gray-100">
      <h1 className="text-2xl font-semibold">Assets</h1>
      <p className="text-gray-300 mt-1">
        MVP focuses on repo activity scoring. Asset graph visualization can be plugged in from the existing IARG services later.
      </p>

      <div className="card mt-6">
        <div className="card-header">
          <div className="text-sm text-gray-300">Monitored (Selected) Repo</div>
          <div className="text-lg font-semibold mt-1">
            {latestQuery.data?.selected_repo || (latestQuery.isLoading ? 'Loading...' : '—')}
          </div>
        </div>
        <div className="card-body text-sm text-gray-200">
          {latestQuery.data?.latest_risk ? (
            <>
              Latest risk score: <span className="font-medium">{latestQuery.data.latest_risk.risk_score.toFixed(1)}</span>{' '}
              ({latestQuery.data.latest_risk.risk_level})
            </>
          ) : (
            'Run a scan to compute the selected repo risk.'
          )}
        </div>
      </div>
    </div>
  )
}

