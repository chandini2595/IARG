import React, { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { guardianApi } from '@/lib/api'

function parseRepos(text: string): string[] {
  return text
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
}

const DRIVE_BREACH_CATEGORIES = [
  { value: 'data_exposure', label: 'Data exposure' },
  { value: 'unauthorized_access', label: 'Unauthorized access' },
  { value: 'ransomware', label: 'Ransomware' },
  { value: 'malware', label: 'Malware' },
  { value: 'other', label: 'Other' },
] as const

function formatApiError(err: any): string {
  const d = err?.response?.data?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) {
    return d
      .map((x: { msg?: string; loc?: unknown }) => x?.msg || JSON.stringify(x))
      .filter(Boolean)
      .join('; ')
  }
  return err?.message || 'Request failed'
}

export default function Settings() {
  const queryClient = useQueryClient()
  const [reposText, setReposText] = useState<string>('facebook/react, tensorflow/tensorflow')
  const [threshold, setThreshold] = useState<number>(70)
  const [windowDays, setWindowDays] = useState<number>(14)

  const [driveResourceId, setDriveResourceId] = useState('')
  const [driveCategory, setDriveCategory] = useState<string>(DRIVE_BREACH_CATEGORIES[0].value)
  const [driveDescription, setDriveDescription] = useState('')
  const [driveWebhookSecret, setDriveWebhookSecret] = useState('')

  const scanMutation = useMutation({
    mutationFn: async () => {
      const candidate_repos = parseRepos(reposText)
      return guardianApi.post('/api/guardian/scan/now', {
        candidate_repos,
        threshold,
        window_days: windowDays,
      })
    },
    onSuccess: async (res: any) => {
      const data = res.data
      toast.success(data?.insurance_triggered ? 'Risk exceeded threshold: insurance triggered.' : 'Scan complete. No insurance triggered.')
      // Keep other pages in sync (Dashboard/RiskScoring/Insurance) after a scan from Settings.
      await queryClient.invalidateQueries({ queryKey: ['guardian-monitor-summary'] })
      await queryClient.invalidateQueries({ queryKey: ['guardian-risk-latest'] })
      await queryClient.invalidateQueries({ queryKey: ['guardian-risk-latest-short'] })
      await queryClient.invalidateQueries({ queryKey: ['guardian-purchases'] })
      await queryClient.invalidateQueries({ queryKey: ['guardian-purchases-all'] })
    },
    onError: (err: any) => {
      toast.error(formatApiError(err) || 'Scan failed')
    },
  })

  const driveBreachMutation = useMutation({
    mutationFn: async () => {
      const headers: Record<string, string> = {}
      if (driveWebhookSecret.trim()) {
        headers['X-IARG-Drive-Breach-Secret'] = driveWebhookSecret.trim()
      }
      return guardianApi.post(
        '/api/guardian/google-drive/breach',
        {
          resource_id: driveResourceId.trim(),
          breach_category: driveCategory,
          description: driveDescription.trim() || undefined,
        },
        { headers },
      )
    },
    onSuccess: async (res: any) => {
      const data = res.data
      if (data?.insurance_triggered) {
        toast.success('Insurance triggered for this Drive resource.')
      } else if (data?.cooldown_applied) {
        toast('Report recorded; insurance skipped (cooldown).', { icon: '⏳' })
      } else {
        toast.success('Breach reported. No insurance trigger (see reason in response if needed).')
      }
      await queryClient.invalidateQueries({ queryKey: ['guardian-monitor-summary'] })
      await queryClient.invalidateQueries({ queryKey: ['guardian-risk-latest'] })
      await queryClient.invalidateQueries({ queryKey: ['guardian-risk-latest-short'] })
      await queryClient.invalidateQueries({ queryKey: ['guardian-purchases'] })
      await queryClient.invalidateQueries({ queryKey: ['guardian-purchases-all'] })
    },
    onError: (err: any) => {
      toast.error(formatApiError(err) || 'Drive breach request failed')
    },
  })

  const driveMonitorQuery = useQuery({
    queryKey: ['guardian-drive-monitor-status'],
    queryFn: async () => (await guardianApi.get('/api/guardian/google-drive/monitor/status')).data,
    refetchInterval: 30_000,
  })

  const drivePollMutation = useMutation({
    mutationFn: async () => {
      const headers: Record<string, string> = {}
      if (driveWebhookSecret.trim()) {
        headers['X-IARG-Drive-Breach-Secret'] = driveWebhookSecret.trim()
      }
      return guardianApi.post('/api/guardian/google-drive/monitor/poll-now', {}, { headers })
    },
    onSuccess: async (res: any) => {
      const d = res.data
      if (d?.skipped) {
        toast(d?.reason || 'Drive poll skipped', { icon: 'ℹ️' })
      } else {
        toast.success(
          `Drive ACL poll: ${d?.resources_checked ?? 0} resources checked, ${d?.breach_reports ?? 0} risk event(s), ${d?.insurance_triggers ?? 0} insurance trigger(s).`,
        )
      }
      await queryClient.invalidateQueries({ queryKey: ['guardian-drive-monitor-status'] })
      await queryClient.invalidateQueries({ queryKey: ['guardian-monitor-summary'] })
      await queryClient.invalidateQueries({ queryKey: ['guardian-risk-latest'] })
      await queryClient.invalidateQueries({ queryKey: ['guardian-risk-latest-short'] })
      await queryClient.invalidateQueries({ queryKey: ['guardian-purchases'] })
      await queryClient.invalidateQueries({ queryKey: ['guardian-purchases-all'] })
    },
    onError: (err: any) => {
      toast.error(formatApiError(err) || 'Drive poll failed')
    },
  })

  return (
    <div className="p-6 min-h-screen bg-gray-950 text-gray-100">
      <h1 className="text-2xl font-semibold">Settings</h1>
      <p className="text-gray-300 mt-1">
        Configure GitHub scans below. Report a Google Drive security incident in the Drive section—no need to use curl unless
        you prefer automation. Optional API monitor (OAuth) reads ACLs periodically—configure via env (see MVP.md).
      </p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-6">
        <div className="card">
          <div className="card-header">
            <div className="text-sm text-gray-300">Candidate Repos</div>
          </div>
          <div className="card-body">
            <label className="block">
              <div className="text-sm text-gray-200 mb-1">Enter `owner/repo` list</div>
              <textarea
                value={reposText}
                onChange={(e) => setReposText(e.target.value)}
                rows={4}
                className="w-full border-gray-800 border rounded-md px-3 py-2 bg-gray-950/30 text-gray-100"
              />
            </label>
            <div className="text-xs text-gray-400 mt-2">
              The MVP scans each repo and selects the “most active” one (commits + open PRs + open issues).
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="text-sm text-gray-300">Threshold & Window</div>
          </div>
          <div className="card-body space-y-3">
            <label className="block">
              <div className="text-sm text-gray-200 mb-1">Risk Threshold (score out of 100)</div>
              <input
                type="number"
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
                className="w-full border-gray-800 border rounded-md px-3 py-2 bg-gray-950/30 text-gray-100"
              />
            </label>
            <label className="block">
              <div className="text-sm text-gray-200 mb-1">Commits Window Days</div>
              <input
                type="number"
                value={windowDays}
                onChange={(e) => setWindowDays(Number(e.target.value))}
                className="w-full border-gray-800 border rounded-md px-3 py-2 bg-gray-950/30 text-gray-100"
              />
            </label>

            <button className="btn btn-primary w-full" onClick={() => scanMutation.mutate()} disabled={scanMutation.isPending}>
              {scanMutation.isPending ? 'Running scan...' : 'Run Scan & Evaluate'}
            </button>
          </div>
        </div>
      </div>

      <div className="card mt-6">
        <div className="card-header">
          <div className="text-sm text-gray-300">Google Drive — API monitor (ACL polling)</div>
          <div className="text-xs text-gray-500 mt-1">
            When enabled on the server, Guardian calls the Drive API with your OAuth refresh token, snapshots permissions, and
            flags <strong>new</strong> risky shares (e.g. “anyone with link”). First poll per file/folder only records a baseline.
            Use <strong>Run ACL poll now</strong> to test; same webhook secret as below if <code className="text-gray-500">DRIVE_BREACH_WEBHOOK_SECRET</code> is set.
          </div>
        </div>
        <div className="card-body space-y-3 text-sm text-gray-200">
          {driveMonitorQuery.isLoading ? (
            <div className="text-gray-400">Loading monitor status…</div>
          ) : driveMonitorQuery.isError ? (
            <div className="text-red-400">Could not load monitor status.</div>
          ) : (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-gray-400">
                <div>
                  Monitor enabled:{' '}
                  <span className="text-gray-200">{driveMonitorQuery.data?.monitor_enabled ? 'yes' : 'no'}</span>
                </div>
                <div>
                  OAuth configured:{' '}
                  <span className="text-gray-200">{driveMonitorQuery.data?.oauth_configured ? 'yes' : 'no'}</span>
                </div>
                <div className="sm:col-span-2">
                  Monitored IDs:{' '}
                  <span className="text-gray-200 break-all">
                    {(driveMonitorQuery.data?.monitored_resource_ids || []).join(', ') || '—'}
                  </span>
                </div>
                <div>
                  Last poll:{' '}
                  <span className="text-gray-200">{driveMonitorQuery.data?.last_poll_at || '—'}</span>
                </div>
                <div>
                  Last OK:{' '}
                  <span className="text-gray-200">
                    {driveMonitorQuery.data?.last_poll_ok === undefined || driveMonitorQuery.data?.last_poll_ok === null
                      ? '—'
                      : driveMonitorQuery.data?.last_poll_ok
                        ? 'yes'
                        : 'no'}
                  </span>
                </div>
                {driveMonitorQuery.data?.last_error ? (
                  <div className="sm:col-span-2 text-amber-400/90 break-words">
                    Error: {driveMonitorQuery.data.last_error}
                  </div>
                ) : null}
              </div>
              <button
                type="button"
                className="btn btn-primary w-full sm:w-auto"
                onClick={() => drivePollMutation.mutate()}
                disabled={drivePollMutation.isPending}
              >
                {drivePollMutation.isPending ? 'Polling…' : 'Run ACL poll now'}
              </button>
            </>
          )}
        </div>
      </div>

      <div className="card mt-6">
        <div className="card-header">
          <div className="text-sm text-gray-300">Google Drive — report breach</div>
          <div className="text-xs text-gray-500 mt-1">
            Use the file or folder ID from the Drive URL (the segment after <code className="text-gray-400">/folders/</code> or{' '}
            <code className="text-gray-400">/file/d/</code>). Insurance uses a critical synthetic score; cooldown still applies per
            Drive resource.
          </div>
        </div>
        <div className="card-body space-y-3">
          <label className="block">
            <div className="text-sm text-gray-200 mb-1">Drive resource ID</div>
            <input
              type="text"
              value={driveResourceId}
              onChange={(e) => setDriveResourceId(e.target.value)}
              placeholder="e.g. 1wkO12VZt0aXQdN3fpm9-6dVMwsC1RCJv"
              className="w-full border-gray-800 border rounded-md px-3 py-2 bg-gray-950/30 text-gray-100 placeholder:text-gray-600"
            />
          </label>
          <label className="block">
            <div className="text-sm text-gray-200 mb-1">Breach category</div>
            <select
              value={driveCategory}
              onChange={(e) => setDriveCategory(e.target.value)}
              className="w-full border-gray-800 border rounded-md px-3 py-2 bg-gray-950/30 text-gray-100"
            >
              {DRIVE_BREACH_CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <div className="text-sm text-gray-200 mb-1">Description (optional)</div>
            <textarea
              value={driveDescription}
              onChange={(e) => setDriveDescription(e.target.value)}
              rows={3}
              placeholder="What happened, when, link to ticket…"
              className="w-full border-gray-800 border rounded-md px-3 py-2 bg-gray-950/30 text-gray-100 placeholder:text-gray-600"
            />
          </label>
          <label className="block">
            <div className="text-sm text-gray-200 mb-1">Webhook secret (optional)</div>
            <input
              type="password"
              autoComplete="off"
              value={driveWebhookSecret}
              onChange={(e) => setDriveWebhookSecret(e.target.value)}
              placeholder="Only if DRIVE_BREACH_WEBHOOK_SECRET is set on the server"
              className="w-full border-gray-800 border rounded-md px-3 py-2 bg-gray-950/30 text-gray-100 placeholder:text-gray-600"
            />
            <div className="text-xs text-gray-500 mt-1">
              Sent as <code className="text-gray-500">X-IARG-Drive-Breach-Secret</code> for manual breach reports and for{' '}
              <strong>Run ACL poll now</strong>. Leave empty when the server secret is not configured.
            </div>
          </label>
          <button
            className="btn btn-primary w-full"
            onClick={() => driveBreachMutation.mutate()}
            disabled={driveBreachMutation.isPending || !driveResourceId.trim()}
          >
            {driveBreachMutation.isPending ? 'Submitting…' : 'Report Drive breach & evaluate insurance'}
          </button>
        </div>
      </div>
    </div>
  )
}

