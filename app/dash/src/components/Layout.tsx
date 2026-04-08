import React from 'react'
import { NavLink } from 'react-router-dom'

type Props = {
  children: React.ReactNode
}

function IconMonitor(props: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={props.className}
    >
      <rect x="3" y="4" width="18" height="14" rx="2" />
      <path d="M8 20h8" />
    </svg>
  )
}

function IconAssets(props: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={props.className}
    >
      <path d="M12 2 2 7l10 5 10-5-10-5Z" />
      <path d="M2 17l10 5 10-5" />
      <path d="M2 12l10 5 10-5" />
    </svg>
  )
}

function IconRisk(props: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={props.className}
    >
      <path d="M4 19V5" />
      <path d="M8 19V11" />
      <path d="M12 19V7" />
      <path d="M16 19V13" />
      <path d="M20 19V9" />
    </svg>
  )
}

function IconInsurance(props: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={props.className}
    >
      <path d="M12 2 20 6v6c0 5-3.4 9.4-8 10-4.6-.6-8-5-8-10V6l8-4Z" />
      <path d="M9.5 12.5 11 14l3.5-4" />
    </svg>
  )
}

function IconSettings(props: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={props.className}
    >
      <path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" />
      <path d="M19.4 15a1.8 1.8 0 0 0 .35 1.98l.05.05a2.2 2.2 0 0 1-1.55 3.75 2.2 2.2 0 0 1-1.55-.64l-.05-.05a1.8 1.8 0 0 0-1.98-.35 1.8 1.8 0 0 0-1.08 1.64V21a2.2 2.2 0 0 1-4.4 0v-.07a1.8 1.8 0 0 0-1.08-1.64 1.8 1.8 0 0 0-1.98.35l-.05.05a2.2 2.2 0 0 1-3.1 0 2.2 2.2 0 0 1 0-3.1l.05-.05A1.8 1.8 0 0 0 4.6 15a1.8 1.8 0 0 0-1.64-1.08H2.9a2.2 2.2 0 0 1 0-4.4h.07A1.8 1.8 0 0 0 4.6 8.54a1.8 1.8 0 0 0-.35-1.98l-.05-.05a2.2 2.2 0 0 1 1.55-3.75 2.2 2.2 0 0 1 1.55.64l.05.05a1.8 1.8 0 0 0 1.98.35 1.8 1.8 0 0 0 1.08-1.64V3a2.2 2.2 0 0 1 4.4 0v.07a1.8 1.8 0 0 0 1.08 1.64 1.8 1.8 0 0 0 1.98-.35l.05-.05a2.2 2.2 0 0 1 3.1 0 2.2 2.2 0 0 1 0 3.1l-.05.05a1.8 1.8 0 0 0-.35 1.98 1.8 1.8 0 0 0 1.64 1.08H21a2.2 2.2 0 0 1 0 4.4h-.07A1.8 1.8 0 0 0 19.4 15Z" />
    </svg>
  )
}

const navItems = [
  { to: '/', label: 'Monitor', Icon: IconMonitor },
  { to: '/assets', label: 'Assets', Icon: IconAssets },
  { to: '/risk-scoring', label: 'Risk Scoring', Icon: IconRisk },
  { to: '/insurance', label: 'Insurance', Icon: IconInsurance },
  { to: '/settings', label: 'Settings', Icon: IconSettings },
]

export default function Layout({ children }: Props) {
  return (
    <div className="flex min-h-screen">
      <aside className="w-64 bg-gray-950/90 backdrop-blur-md border-r border-primary-500/15 shadow-[0_0_40px_rgba(59,130,246,0.10)] min-h-screen">
        <div className="p-6">
          <div className="flex items-center gap-3">
            <img
              src="/iarg-logo.png"
              alt="IARG logo"
              className="w-10 h-10 object-contain"
            />
            <div className="text-lg font-semibold">IARG</div>
          </div>
          <div className="text-sm text-gray-300 mt-1">Intangible-Asset Risk Guardian</div>

          <div className="mt-4 flex items-center gap-2 text-xs text-gray-200/90">
            <span className="inline-flex w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_18px_rgba(52,211,153,0.55)] animate-pulse" />
            <span>Live Monitor</span>
          </div>
        </div>

        <nav className="px-3 pb-6 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                [
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium border transition-all duration-150',
                  isActive
                    ? 'bg-primary-500/15 border-primary-500/40 text-primary-200 shadow-[0_0_24px_rgba(59,130,246,0.25)] border-l-4 border-l-primary-500/80 pl-[11px]'
                    : 'bg-transparent border-transparent text-gray-200/90 hover:bg-white/5 hover:border-gray-700 border-l-4 border-l-transparent pl-[15px]',
                ].join(' ')
              }
            >
              <item.Icon className="w-5 h-5 shrink-0" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="flex-1 text-gray-100">{children}</main>
    </div>
  )
}

