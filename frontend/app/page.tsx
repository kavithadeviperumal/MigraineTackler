'use client'

import { useRouter } from 'next/navigation'
import { useEffect } from 'react'

import { useAuth } from '@/contexts/auth-context'

export default function RootPage() {
  const { isAuthenticated } = useAuth()
  const router = useRouter()

  useEffect(() => {
    router.replace(isAuthenticated ? '/dashboard' : '/login')
  }, [isAuthenticated, router])

  return null
}