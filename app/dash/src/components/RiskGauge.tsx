import React, { useMemo } from 'react'

type Props = {
  value: number
  label?: string
  size?: number
  valueText?: string
}

/**
 * Simple SVG circular gauge (no external charting dependency).
 * value is expected to be in [0, 100].
 */
export default function RiskGauge({ value, label = 'Risk', size = 96, valueText }: Props) {
  const pct = useMemo(() => {
    if (Number.isNaN(value)) return 0
    return Math.max(0, Math.min(100, value))
  }, [value])

  const strokeWidth = 10
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const dashOffset = circumference * (1 - pct / 100)

  return (
    <div className="flex items-center gap-4">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="block">
          <defs>
            <linearGradient id="riskGaugeGradient" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#22c55e" />
              <stop offset="50%" stopColor="#f59e0b" />
              <stop offset="100%" stopColor="#ef4444" />
            </linearGradient>
          </defs>

          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="#e5e7eb"
            strokeWidth={strokeWidth}
            fill="none"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="url(#riskGaugeGradient)"
            strokeWidth={strokeWidth}
            fill="none"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
          />
        </svg>

        <div className="absolute inset-0 flex items-center justify-center flex-col">
          <div className="text-xl font-semibold leading-tight">{valueText ?? pct.toFixed(0)}</div>
          <div className="text-[11px] text-gray-500 -mt-1">{label}</div>
        </div>
      </div>
    </div>
  )
}

