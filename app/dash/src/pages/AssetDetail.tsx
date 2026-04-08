import React from 'react'
import { useParams } from 'react-router-dom'

export default function AssetDetail() {
  const { id } = useParams<{ id: string }>()

  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold">Asset Detail</h1>
      <p className="text-gray-600 mt-1 text-sm">MVP placeholder. Full asset graph integration will connect to the Neo4j-based IARG graph service.</p>

      <div className="card mt-6">
        <div className="card-header">
          <div className="text-sm text-gray-600">Asset ID</div>
          <div className="text-lg font-semibold mt-1">{id || '—'}</div>
        </div>
        <div className="card-body text-sm text-gray-700">Not implemented yet in MVP.</div>
      </div>
    </div>
  )
}

