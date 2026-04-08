import React, { useMemo } from 'react'

type Props = {
  value?: number | null
  threshold: number
  label?: string
}

/**
 * Horizontal threshold meter for risk scores in [0..100].
 */
export default function ThresholdMeter({ value, threshold, label }: Props) {
  const { pctValue, pctThreshold, filledColor } = useMemo(() => {
    const v = typeof value === 'number' && Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : 0
    const t = Math.max(0, Math.min(100, threshold))

    const color =
      v >= 0.99 * t ? '#ef4444' : v >= 0.75 * t ? '#f59e0b' : '#22c55e'

    return { pctValue: v, pctThreshold: t, filledColor: color }
  }, [value, threshold])

  return (
    <div className="space-y-2">
      {label ? <div className="text-sm text-gray-600">{label}</div> : null}
      <div className="relative h-3 rounded-full bg-gray-100 border border-gray-200 overflow-hidden">
        <div
          className="absolute inset-y-0 left-0"
          style={{
            width: `${pctValue}%`,
            background: `linear-gradient(90deg, ${filledColor}, #3b82f6)`,
          }}
        />
        {/* Threshold marker */}
        <div
          className="absolute top-0 bottom-0"
          style={{
            left: `${pctThreshold}%`,
            width: 2,
            background: '#111827',
            opacity: 0.35,
          }}
        />
      </div>
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>{typeof value === 'number' ? `${value.toFixed(1)} / 100` : '— / 100'}</span>
        <span>Threshold: {threshold.toFixed(0)}</span>
      </div>
    </div>
  )
}

