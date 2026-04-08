import { format } from 'date-fns'

// The backend sends ISO datetimes sometimes with >3 fractional digits
// (e.g. `2026-03-18T20:25:20.699400`), which `Date` may not parse consistently.
function normalizeIsoForJs(iso: string): string {
  // If there's a fractional seconds part with >3 digits, trim to 3 (milliseconds).
  return iso.replace(/(\.\d{3})\d+/, '$1')
}

export function formatDateTime(iso?: string | null, pattern = 'yyyy-MM-dd HH:mm:ss'): string {
  if (!iso) return '—'
  const normalized = normalizeIsoForJs(iso)
  const d = new Date(normalized)
  if (Number.isNaN(d.getTime())) return iso
  return format(d, pattern)
}

