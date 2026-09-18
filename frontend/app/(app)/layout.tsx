'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'

import { useAuth } from '@/contexts/auth-context'

const NAV = [
  { href: '/log', label: 'Log Entry', icon: '📋' },
  { href: '/dashboard', label: 'Dashboard', icon: '📊' },
  { href: '/research', label: 'Research', icon: '🔬' },
  { href: '/history', label: 'History', icon: '📅' },
  { href: '/settings', label: 'Settings', icon: '⚙️' },
]

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, isAuthenticated, logout } = useAuth()
  const router = useRouter()
  const pathname = usePathname()
  const [hydrated, setHydrated] = useState(false)

  useEffect(() => setHydrated(true), [])

  useEffect(() => {
    if (hydrated && !isAuthenticated) router.replace('/login')
  }, [hydrated, isAuthenticated, router])

  if (!hydrated || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="h-6 w-6 rounded-full border-2 border-primary border-t-transparent animate-spin" />
      </div>
    )
  }

  function handleLogout() {
    logout()
    router.replace('/login')
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="w-60 shrink-0 flex flex-col bg-sidebar border-r border-sidebar-border">
        <div className="px-5 py-4 border-b border-sidebar-border">
          <span className="font-semibold tracking-tight text-sidebar-foreground">
            🧠 MigraineTackler
          </span>
        </div>

        <nav className="flex-1 px-2 py-3 space-y-0.5">
          {NAV.map(({ href, label, icon }) => {
            const active = pathname === href || pathname.startsWith(`${href}/`)
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                  active
                    ? 'bg-sidebar-accent text-sidebar-accent-foreground font-medium'
                    : 'text-sidebar-foreground hover:bg-sidebar-accent/60'
                }`}
              >
                <span className="text-base leading-none">{icon}</span>
                <span>{label}</span>
              </Link>
            )
          })}
        </nav>

        <div className="px-2 py-3 border-t border-sidebar-border space-y-0.5">
          <p className="px-3 py-1.5 text-xs text-muted-foreground">
            {user?.username}
          </p>
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-sidebar-foreground hover:bg-sidebar-accent/60 transition-colors"
          >
            <span className="text-base leading-none">🚪</span>
            <span>Log out</span>
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  )
}