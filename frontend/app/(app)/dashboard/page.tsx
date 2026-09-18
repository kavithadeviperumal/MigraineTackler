'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import { useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { type AnalyzeResponse, type LogEntry, analyze, logs } from '@/lib/api'

const RISK_EMOJI: Record<string, string> = {
  low: '🟢',
  moderate: '🟡',
  high: '🟠',
  critical: '🔴',
}

const RISK_BAR: Record<string, string> = {
  low: 'bg-chart-1',
  moderate: 'bg-chart-2',
  high: 'bg-chart-3',
  critical: 'bg-destructive',
}

const SOURCE_ICON: Record<string, string> = {
  log_history: '🗓',
  onboarding: '📋',
  weather: '🌦',
  agent_memory: '🧠',
  stats: '📊',
}

function calcStreak(logList: LogEntry[]): number {
  const sorted = [...logList].sort((a, b) => b.entry_date.localeCompare(a.entry_date))
  let streak = 0
  for (const log of sorted) {
    if (log.migraine_occurred) break
    streak++
  }
  return streak
}

export default function DashboardPage() {
  const queryClient = useQueryClient()
  const [auditOutput, setAuditOutput] = useState<string | null>(null)
  const [patternMsg, setPatternMsg] = useState<string | null>(null)
  const [rootCauseMsg, setRootCauseMsg] = useState<string | null>(null)
  const [protocolMsg, setProtocolMsg] = useState<string | null>(null)

  const { data: logList = [], isLoading: logsLoading } = useQuery({
    queryKey: ['logs', 60],
    queryFn: () => logs.list(60),
  })

  const { data: toxicLoad } = useQuery({
    queryKey: ['toxic-load'],
    queryFn: () => logs.toxicLoad(),
  })

  const { data: analyzeState } = useQuery({
    queryKey: ['analyze-state'],
    queryFn: () => analyze.state(),
  })

  const refreshState = () =>
    queryClient.invalidateQueries({ queryKey: ['analyze-state'] })

  const auditMutation = useMutation({
    mutationFn: () => analyze.run('lifestyle_audit'),
    onSuccess: (data: AnalyzeResponse) => {
      const msgs = data.messages ?? []
      setAuditOutput(msgs.at(-1) ?? null)
    },
  })

  const patternMutation = useMutation({
    mutationFn: () => analyze.run('pattern_review'),
    onSuccess: () => {
      setPatternMsg('Pattern analysis complete — triggers updated.')
      void refreshState()
    },
  })

  const rootCauseMutation = useMutation({
    mutationFn: () => analyze.run('root_cause_review'),
    onSuccess: () => {
      setRootCauseMsg('Root cause analysis complete — hypothesis updated.')
      void refreshState()
    },
  })

  const protocolMutation = useMutation({
    mutationFn: () => analyze.run('protocol_review'),
    onSuccess: () => {
      setProtocolMsg('Protocol generated.')
      void refreshState()
    },
  })

  // Computed metrics
  const last30 = logList.slice(0, 30)
  const migraineDays = last30.filter((l) => l.migraine_occurred)
  const painScores = migraineDays
    .map((l) => l.pain_level)
    .filter((p): p is number => p != null)
  const avgPain = painScores.length
    ? painScores.reduce((a, b) => a + b, 0) / painScores.length
    : null
  const streak = calcStreak(logList)

  const risk = toxicLoad?.risk_level ?? 'low'
  const fillPct = Math.min(toxicLoad?.fill_pct ?? 0, 100)

  const confirmedTriggers = analyzeState?.confirmed_triggers ?? []
  const suspectedTriggers = analyzeState?.suspected_triggers ?? []
  const hypothesis = analyzeState?.current_root_cause_hypothesis
  const evidence = analyzeState?.root_cause_evidence ?? []
  const subtype = analyzeState?.migraine_subtype
  const protocol = analyzeState?.current_protocol

  if (logsLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="h-6 w-6 rounded-full border-2 border-primary border-t-transparent animate-spin" />
      </div>
    )
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <Link href="/log" className={buttonVariants({ variant: 'default', size: 'sm' })}>
          Log Today
        </Link>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <MetricCard label="Migraines (30d)" value={String(migraineDays.length)} />
        <MetricCard
          label="Avg Pain (30d)"
          value={avgPain != null ? `${avgPain.toFixed(1)}/10` : '—'}
        />
        <MetricCard label="Total Logs" value={String(logList.length)} />
        <MetricCard label="Migraine-free streak" value={`${streak}d`} />
      </div>

      {/* Toxic Load */}
      {toxicLoad && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>
                {RISK_EMOJI[risk]} Trigger Bucket
              </CardTitle>
              <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                {risk}
              </span>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>
                  Rolling:{' '}
                  <strong className="text-foreground">{toxicLoad.rolling_score}</strong> /{' '}
                  {toxicLoad.threshold} threshold · Today: {toxicLoad.today_score} ·
                  Carry-over: {toxicLoad.carryover_score}
                </span>
                <span>{fillPct.toFixed(0)}%</span>
              </div>
              <div className="h-2.5 w-full bg-muted rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${RISK_BAR[risk]}`}
                  style={{ width: `${fillPct}%` }}
                />
              </div>
            </div>
            {Object.keys(toxicLoad.breakdown).length > 0 ? (
              <p className="text-xs text-muted-foreground">
                Today&apos;s contributors:{' '}
                {Object.entries(toxicLoad.breakdown)
                  .sort(([, a], [, b]) => b - a)
                  .map(([k, v], i) => (
                    <span key={k}>
                      {i > 0 && '  ·  '}
                      <strong className="text-foreground">{k.replaceAll('_', ' ')}</strong> +{v}
                    </span>
                  ))}
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">No triggers logged today.</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Triggers + Root Cause */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Triggers</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {confirmedTriggers.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Confirmed
                </p>
                {confirmedTriggers.map((t) => (
                  <div key={t} className="flex items-center gap-2 text-sm">
                    <span>🔴</span>
                    <span>{t}</span>
                  </div>
                ))}
              </div>
            )}
            {confirmedTriggers.length > 0 && suspectedTriggers.length > 0 && (
              <Separator />
            )}
            {suspectedTriggers.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Suspected
                </p>
                {suspectedTriggers.map((t) => (
                  <div key={t} className="flex items-center gap-2 text-sm">
                    <span>🟡</span>
                    <span>{t}</span>
                  </div>
                ))}
              </div>
            )}
            {confirmedTriggers.length === 0 && suspectedTriggers.length === 0 && (
              <p className="text-sm text-muted-foreground">No triggers identified yet.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Root Cause Hypothesis</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {hypothesis ? (
              <>
                {subtype && (
                  <Badge variant="outline" className="text-xs">
                    {subtype}
                  </Badge>
                )}
                <p className="text-sm leading-relaxed">{hypothesis}</p>
                {evidence.length > 0 && (
                  <>
                    <Separator />
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                      Evidence
                    </p>
                    <div className="space-y-1.5">
                      {evidence.map((ev, i) => (
                        <div key={i} className="flex gap-2 text-sm">
                          <span className="shrink-0">{SOURCE_ICON[ev.source_type] ?? '•'}</span>
                          <span>
                            {ev.claim}{' '}
                            <code className="text-xs text-muted-foreground bg-muted px-1 py-0.5 rounded">
                              {ev.source}
                            </code>
                          </span>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </>
            ) : (
              <p className="text-sm text-muted-foreground">No hypothesis yet.</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Protocol */}
      <Card>
        <CardHeader>
          <CardTitle>Current Protocol</CardTitle>
        </CardHeader>
        <CardContent>
          {protocol?.active_items?.length ? (
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground mb-3">
                Version {protocol.version} · {protocol.date}
              </p>
              {protocol.active_items.map((item, i) => (
                <details key={i} className="group">
                  <summary className="flex items-center gap-3 cursor-pointer list-none py-2 px-3 rounded-lg hover:bg-accent/40 text-sm transition-colors">
                    <Badge variant="outline" className="text-xs shrink-0">
                      Tier {item.tier}
                    </Badge>
                    <span className="font-medium">{item.intervention}</span>
                    <span className="ml-auto text-muted-foreground text-xs group-open:rotate-180 transition-transform">
                      ▾
                    </span>
                  </summary>
                  <div className="mt-1 ml-4 px-3 py-2.5 space-y-1.5 text-sm border-l border-border/60">
                    <p>
                      <span className="text-muted-foreground">Detail: </span>
                      {item.dose_or_detail}
                    </p>
                    <p>
                      <span className="text-muted-foreground">Rationale: </span>
                      {item.rationale}
                    </p>
                    <p>
                      <span className="text-muted-foreground">What to log: </span>
                      {item.what_to_log}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Assess after {item.assessment_weeks} weeks
                    </p>
                  </div>
                </details>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No protocol yet.</p>
          )}
        </CardContent>
      </Card>

      {/* Lifestyle Audit */}
      <Card>
        <CardHeader>
          <CardTitle>Lifestyle Audit</CardTitle>
          <CardDescription>
            On-demand: what&apos;s slipping, what worked, and non-medication protocols grounded in
            your data.
          </CardDescription>
          <CardAction>
            <Button
              variant="outline"
              size="sm"
              onClick={() => auditMutation.mutate()}
              disabled={auditMutation.isPending}
            >
              {auditMutation.isPending ? 'Analyzing…' : 'Run Audit'}
            </Button>
          </CardAction>
        </CardHeader>
        {auditOutput && (
          <CardContent>
            <div className="text-sm leading-relaxed whitespace-pre-wrap border-t border-border pt-4 mt-1">
              {auditOutput}
            </div>
          </CardContent>
        )}
        {auditMutation.isError && (
          <CardContent>
            <p className="text-sm text-destructive">
              Failed to run audit. Please try again.
            </p>
          </CardContent>
        )}
      </Card>

      {/* Analysis buttons */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <AnalysisCard
          label="Run Pattern Analysis"
          loadingLabel="Analyzing patterns…"
          isPending={patternMutation.isPending}
          successMsg={patternMsg}
          isError={patternMutation.isError}
          onClick={() => patternMutation.mutate()}
        />
        <AnalysisCard
          label="Run Root Cause Analysis"
          loadingLabel="Analyzing root cause…"
          isPending={rootCauseMutation.isPending}
          successMsg={rootCauseMsg}
          isError={rootCauseMutation.isError}
          onClick={() => rootCauseMutation.mutate()}
        />
        <AnalysisCard
          label="Generate Protocol"
          loadingLabel="Generating protocol…"
          isPending={protocolMutation.isPending}
          successMsg={protocolMsg}
          isError={protocolMutation.isError}
          onClick={() => protocolMutation.mutate()}
        />
      </div>
    </div>
  )
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="pt-1">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-2xl font-bold mt-1 tabular-nums">{value}</p>
      </CardContent>
    </Card>
  )
}

function AnalysisCard({
  label,
  loadingLabel,
  isPending,
  successMsg,
  isError,
  onClick,
}: {
  label: string
  loadingLabel: string
  isPending: boolean
  successMsg: string | null
  isError: boolean
  onClick: () => void
}) {
  return (
    <Card>
      <CardContent className="pt-1 flex flex-col gap-2">
        <Button variant="outline" className="w-full" onClick={onClick} disabled={isPending}>
          {isPending ? loadingLabel : label}
        </Button>
        {successMsg && <p className="text-xs text-center text-muted-foreground">{successMsg}</p>}
        {isError && (
          <p className="text-xs text-center text-destructive">Failed. Please try again.</p>
        )}
      </CardContent>
    </Card>
  )
}