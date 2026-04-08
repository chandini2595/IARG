import React, { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { guardianApi } from '@/lib/api'
import toast from 'react-hot-toast'
import { formatDateTime } from '@/lib/formatDateTime'

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

type Evidence = {
  evidence_id: string
  purchase_id: string
  evidence: any
  created_at: string
}

type PurchaseDetail = {
  purchase: Purchase
  evidence: Evidence
}

export default function Insurance() {
  const [selectedPurchaseId, setSelectedPurchaseId] = useState<string | null>(null)

  const purchasesQuery = useQuery({
    queryKey: ['guardian-purchases-all'],
    queryFn: async () => {
      const res = await guardianApi.get('/api/guardian/insurance/purchases?limit=50&offset=0')
      return (res.data?.purchases || []) as Purchase[]
    },
  })

  const selectedPurchase = useMemo(() => {
    return purchasesQuery.data?.find((p) => p.purchase_id === selectedPurchaseId) || null
  }, [purchasesQuery.data, selectedPurchaseId])

  const [detail, setDetail] = useState<PurchaseDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  async function loadDetail(purchaseId: string) {
    try {
      setLoadingDetail(true)
      const res = await guardianApi.get(`/api/guardian/insurance/purchases/${purchaseId}`)
      setDetail(res.data as PurchaseDetail)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to load evidence')
    } finally {
      setLoadingDetail(false)
    }
  }

  return (
    <div className="p-6 min-h-screen bg-gray-950 text-gray-100">
      <h1 className="text-2xl font-semibold">Insurance</h1>
      <p className="text-gray-300 mt-1">
        When risk crosses the threshold, IARG triggers simulated micro/parametric policies and stores claim evidence.
      </p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-6">
        <div className="card">
          <div className="card-header">
            <div className="text-sm text-gray-300">Purchases</div>
            <div className="text-sm text-gray-400">
              {purchasesQuery.data ? `${purchasesQuery.data.length} total` : ''}
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
                      <th className="py-2">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {purchasesQuery.data.map((p) => (
                      <tr key={p.purchase_id} className="border-t border-gray-800 hover:bg-primary-50/20 transition-colors">
                        <td className="py-2 font-medium">{p.repo_full_name}</td>
                        <td className="py-2">{p.policy_name}</td>
                        <td className="py-2">
                          <button
                            className="btn btn-secondary"
                            onClick={async () => {
                              setSelectedPurchaseId(p.purchase_id)
                              await loadDetail(p.purchase_id)
                            }}
                          >
                            {selectedPurchaseId === p.purchase_id ? 'Reload' : 'View Evidence'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-gray-300 text-sm">No purchases yet.</div>
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="text-sm text-gray-300">Evidence</div>
            <div className="text-sm text-gray-400">{selectedPurchase ? selectedPurchase.policy_id : ''}</div>
          </div>
          <div className="card-body">
            {loadingDetail ? (
              <div className="text-gray-300">Loading evidence...</div>
            ) : detail ? (
              <div className="space-y-3">
                <div className="text-sm text-gray-300">Purchase</div>
                <div className="text-sm font-medium">{detail.purchase.policy_name}</div>
                <div className="text-xs text-gray-300">
                  triggered_at: {formatDateTime(detail.purchase.triggered_at)}
                </div>

                <div className="bg-gray-950/40 border border-gray-800 rounded-md p-3">
                  <div className="text-sm font-medium mb-2 text-gray-100">Stored Evidence (JSON)</div>
                  <pre className="text-xs whitespace-pre-wrap text-gray-100">
                    {JSON.stringify(detail.evidence.evidence, null, 2)}
                  </pre>
                </div>
              </div>
            ) : (
              <div className="text-gray-300 text-sm">Select a purchase to view evidence.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

