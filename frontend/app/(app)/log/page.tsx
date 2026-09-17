'use client'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { type LogCreatePayload, analyze, logs, profile } from '@/lib/api'
import {
  ALL_MEDICATIONS,
  CAFFEINE_MG,
  HYDRATION_MULT,
  PAIN_LOCATIONS,
  PRODROME_OPTIONS,
  RELIEF_METHODS,
  SOS_QUICK_MEDS,
  showsCycleDay,
} from '@/lib/constants'

// ── Types ──────────────────────────────────────────────────────────────────────

interface SosPendingData {
  entry_date: string
  pain_level: number
  medication: string | null
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function localToday(): string {
  const d = new Date()
  return (
    d.getFullYear() +
    '-' +
    String(d.getMonth() + 1).padStart(2, '0') +
    '-' +
    String(d.getDate()).padStart(2, '0')
  )
}

function calcSleepHours(bedtime: string | null | undefined, wake: string | null | undefined): number | null {
  if (!bedtime || !wake) return null
  const [bh, bm] = bedtime.split(':').map(Number)
  const [wh, wm] = wake.split(':').map(Number)
  let delta = wh * 60 + wm - (bh * 60 + bm)
  if (delta < 0) delta += 24 * 60
  return Math.round((delta / 60) * 10) / 10
}


function getDynamicLabel(confirmed: string[], suspected: string[]): string {
  const all = [...confirmed, ...suspected]
  if (!all.length) return 'Anything unusual in your environment, diet, or routine in the past 24 hours?'
  const top = all[0].toLowerCase()
  if (['sleep', 'insomnia'].some((k) => top.includes(k)))
    return "Sleep is one of your top triggers — did the previous night feel worse than usual, beyond what's shown above?"
  if (['caffeine', 'coffee'].some((k) => top.includes(k)))
    return "Caffeine is a suspected trigger — did you skip or significantly reduce it today?"
  if (top.includes('stress'))
    return "Stress is linked to your migraines — what was weighing on you in the past 24 hours?"
  if (['weather', 'pressure', 'barometric'].some((k) => top.includes(k)))
    return "Weather changes are a trigger for you — did you notice the headache building with any weather shift?"
  if (['hormonal', 'menstrual', 'cycle'].some((k) => top.includes(k)))
    return "Hormonal patterns are a factor for you — where are you in your cycle right now (day number if known)?"
  return `One of your triggers is ${all[0]} — any exposure to it in the past 24 hours?`
}

function loadSosPending(): SosPendingData | null {
  try {
    const raw = localStorage.getItem('mt_sos_pending')
    return raw ? (JSON.parse(raw) as SosPendingData) : null
  } catch {
    return null
  }
}

function saveSosPending(data: SosPendingData) {
  localStorage.setItem('mt_sos_pending', JSON.stringify(data))
}

function clearSosPending() {
  localStorage.removeItem('mt_sos_pending')
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function PillToggle({
  options,
  selected,
  onChange,
}: {
  options: readonly string[]
  selected: string[]
  onChange: (v: string[]) => void
}) {
  function toggle(opt: string) {
    onChange(selected.includes(opt) ? selected.filter((s) => s !== opt) : [...selected, opt])
  }
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          onClick={() => toggle(opt)}
          className={`px-3 py-1 rounded-full text-xs border transition-colors ${
            selected.includes(opt)
              ? 'bg-primary text-primary-foreground border-primary'
              : 'border-border text-muted-foreground hover:border-primary/50 hover:text-foreground'
          }`}
        >
          {opt.replaceAll('_', ' ')}
        </button>
      ))}
    </div>
  )
}

function RadioPills({
  options,
  value,
  onChange,
  labels,
}: {
  options: readonly string[]
  value: string
  onChange: (v: string) => void
  labels?: Record<string, string>
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          onClick={() => onChange(opt)}
          className={`px-3 py-1 rounded-full text-xs border transition-colors ${
            value === opt
              ? 'bg-primary text-primary-foreground border-primary'
              : 'border-border text-muted-foreground hover:border-primary/50 hover:text-foreground'
          }`}
        >
          {labels?.[opt] ?? opt.replaceAll('_', ' ')}
        </button>
      ))}
    </div>
  )
}

function SliderField({
  label,
  value,
  min = 1,
  max = 10,
  step = 1,
  onChange,
  hint,
}: {
  label: string
  value: number
  min?: number
  max?: number
  step?: number
  onChange: (v: number) => void
  hint?: string
}) {
  return (
    <div className="space-y-2">
      <div className="flex justify-between items-baseline">
        <Label className="text-sm">{label}</Label>
        <span className="text-sm font-semibold tabular-nums text-primary">{value}{hint}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-1.5 bg-muted rounded-full appearance-none cursor-pointer accent-primary"
      />
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{min}</span>
        <span>{max}</span>
      </div>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function LogPage() {
  const queryClient = useQueryClient()

  // ── Data ──
  const { data: profileData } = useQuery({
    queryKey: ['profile'],
    queryFn: () => profile.get(),
  })
  const { data: recentLogs = [] } = useQuery({
    queryKey: ['logs', 5],
    queryFn: () => logs.list(5),
  })
  const { data: analyzeState } = useQuery({
    queryKey: ['analyze-state'],
    queryFn: () => analyze.state(),
  })

  // ── Phase & SOS ──
  const [phase, setPhase] = useState<'form' | 'intake-chat'>('form')
  const [sosPending, setSosPending] = useState<SosPendingData | null>(null)

  useEffect(() => {
    const saved = loadSosPending()
    if (saved) {
      setSosPending(saved)
      setMigraineOccurred(true)
      setEntryDate(saved.entry_date)
    }
  }, [])

  // ── Form core ──
  const today = localToday()
  const [entryDate, setEntryDate] = useState(today)
  const [migraineOccurred, setMigraineOccurred] = useState(false)

  const isPast = entryDate < today
  const showDetailed = migraineOccurred && (isPast || sosPending != null)

  // Clear SOS if user switches to past date
  useEffect(() => {
    if (isPast && sosPending) {
      setSosPending(null)
      clearSosPending()
    }
  }, [entryDate]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Free-day form state ──
  const defaultStress = profileData?.typical_stress_level ?? 3
  const [sleepQuality, setSleepQuality] = useState(6)
  const [stressLevel, setStressLevel] = useState(defaultStress)
  const [selectedFoods, setSelectedFoods] = useState<string[]>([])
  const [hydrationChoice, setHydrationChoice] = useState<'good' | 'average' | 'low'>('average')
  const [freeNotes, setFreeNotes] = useState('')

  // ── SOS quick form state ──
  const [sosQuickPain, setSosQuickPain] = useState(7)
  const [sosQuickMed, setSosQuickMed] = useState('None yet')

  // ── Detailed form state ──
  const [prodromes, setProdromes] = useState<string[]>([])
  const [detailPainLevel, setDetailPainLevel] = useState(sosPending?.pain_level ?? 7)
  const [painLocation, setPainLocation] = useState('')
  const [durationHours, setDurationHours] = useState<number>(0)
  const [reliefMethods, setReliefMethods] = useState<string[]>([])
  const [reliefEffectiveness, setReliefEffectiveness] = useState(5)
  const [medications, setMedications] = useState<string[]>([])
  const [dynamicAnswer, setDynamicAnswer] = useState('')
  const [cycleDay, setCycleDay] = useState<number>(0)

  // Pre-fill medications from SOS quick capture
  useEffect(() => {
    if (sosPending?.medication && (ALL_MEDICATIONS as ReadonlyArray<string>).includes(sosPending.medication)) {
      setMedications([sosPending.medication])
    }
    if (sosPending?.pain_level) {
      setDetailPainLevel(sosPending.pain_level)
    }
  }, [sosPending])

  // Auto-derived context from most recent non-migraine log
  const yesterdayLog = recentLogs.find((l) => !l.migraine_occurred) ?? null
  const profileSleepHours = calcSleepHours(profileData?.typical_bedtime, profileData?.typical_wake_time)
  const profileHydrationOz = profileData?.typical_hydration_oz ?? 64
  const profileCaffeineMg = CAFFEINE_MG[profileData?.typical_caffeine_level ?? 'moderate'] ?? 200

  const autoSleepHours = yesterdayLog?.sleep_hours ?? profileSleepHours
  const autoSleepQuality = yesterdayLog?.sleep_quality ?? null
  const autoStress = yesterdayLog?.stress_level ?? null
  const autoHydrationOz = yesterdayLog?.hydration_oz ?? profileHydrationOz
  const autoCaffeineMg = yesterdayLog?.caffeine_mg ?? profileCaffeineMg
  const autoFoods = yesterdayLog?.foods ?? []

  // ── Chat state ──
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatInput, setChatInput] = useState('')
  const [redFlag, setRedFlag] = useState(false)
  const [mohAlert, setMohAlert] = useState(false)
  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages])

  // ── Submission ──
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [isReplying, setIsReplying] = useState(false)

  async function handleSubmit(payload: LogCreatePayload) {
    setIsSubmitting(true)
    setSubmitError(null)
    try {
      const logResult = await logs.create(payload)
      setRedFlag(logResult.red_flag)
      setMohAlert(logResult.moh_alert)
      const analysis = await analyze.run('log_entry', { logId: logResult.log.id })
      setChatMessages((analysis.messages ?? []).map((m) => ({ role: 'assistant' as const, content: m })))
      clearSosPending()
      setSosPending(null)
      queryClient.invalidateQueries({ queryKey: ['logs'] })
      queryClient.invalidateQueries({ queryKey: ['toxic-load'] })
      setPhase('intake-chat')
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to save. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  function submitFreeDay() {
    handleSubmit({
      entry_date: entryDate,
      migraine_occurred: false,
      sleep_hours: profileSleepHours ?? undefined,
      sleep_quality: sleepQuality,
      stress_level: stressLevel,
      foods: selectedFoods.length ? selectedFoods : undefined,
      hydration_oz: Math.round(profileHydrationOz * HYDRATION_MULT[hydrationChoice]),
      notes: freeNotes || undefined,
    })
  }

  function submitSosQuick() {
    const payload: LogCreatePayload = {
      entry_date: entryDate,
      migraine_occurred: true,
      pain_level: sosQuickPain,
      medications: sosQuickMed !== 'None yet' ? [sosQuickMed] : undefined,
    }
    logs
      .create(payload)
      .then((result) => {
        const data: SosPendingData = {
          entry_date: entryDate,
          pain_level: sosQuickPain,
          medication: sosQuickMed !== 'None yet' ? sosQuickMed : null,
        }
        saveSosPending(data)
        setSosPending(data)
        setDetailPainLevel(sosQuickPain)
        if (data.medication && (ALL_MEDICATIONS as ReadonlyArray<string>).includes(data.medication)) {
          setMedications([data.medication])
        }
        queryClient.invalidateQueries({ queryKey: ['logs'] })
        // Show red flag / MOH from quick capture
        if (result.red_flag) setRedFlag(true)
        if (result.moh_alert) setMohAlert(true)
      })
      .catch((err) => {
        setSubmitError(err instanceof Error ? err.message : 'Failed to save.')
      })
  }

  function submitDetailed() {
    const sosDate = sosPending?.entry_date ?? entryDate
    const notesParts: string[] = []
    if (dynamicAnswer.trim()) {
      notesParts.push(`[Trigger check] ${getDynamicLabel(analyzeState?.confirmed_triggers ?? [], analyzeState?.suspected_triggers ?? [])} — ${dynamicAnswer.trim()}`)
    }
    handleSubmit({
      entry_date: sosDate,
      migraine_occurred: true,
      city: profileData?.home_city ?? undefined,
      pain_level: detailPainLevel,
      pain_location: painLocation || undefined,
      duration_hours: durationHours || undefined,
      prodrome_symptoms: prodromes.length ? prodromes : undefined,
      sleep_hours: autoSleepHours ?? undefined,
      sleep_quality: autoSleepQuality ?? undefined,
      stress_level: autoStress ?? undefined,
      foods: autoFoods.length ? autoFoods : undefined,
      hydration_oz: autoHydrationOz ?? undefined,
      caffeine_mg: autoCaffeineMg ?? undefined,
      medications: medications.length ? medications : undefined,
      relief_methods: reliefMethods.length ? reliefMethods : undefined,
      relief_effectiveness: reliefMethods.length ? reliefEffectiveness : undefined,
      menstrual_cycle_day:
        showsCycleDay(profileData?.hormonal_status) && cycleDay ? cycleDay : undefined,
      notes: notesParts.join('\n') || undefined,
    })
  }

  async function handleChatReply() {
    const msg = chatInput.trim()
    if (!msg) return
    setChatInput('')
    setChatMessages((prev) => [...prev, { role: 'user', content: msg }])
    setIsReplying(true)
    try {
      const analysis = await analyze.run('log_entry', { message: msg })
      setChatMessages((prev) => [
        ...prev,
        ...(analysis.messages ?? []).map((m) => ({ role: 'assistant' as const, content: m })),
      ])
    } catch {
      setChatMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Something went wrong. Please try again.' },
      ])
    } finally {
      setIsReplying(false)
    }
  }

  function resetForm() {
    setPhase('form')
    setMigraineOccurred(false)
    setEntryDate(today)
    setSosPending(null)
    setChatMessages([])
    setRedFlag(false)
    setMohAlert(false)
    setSubmitError(null)
    // Reset form fields
    setSleepQuality(6)
    setStressLevel(profileData?.typical_stress_level ?? 3)
    setSelectedFoods([])
    setHydrationChoice('average')
    setFreeNotes('')
    setSosQuickPain(7)
    setSosQuickMed('None yet')
    setProdromes([])
    setDetailPainLevel(7)
    setPainLocation('')
    setDurationHours(0)
    setReliefMethods([])
    setReliefEffectiveness(5)
    setMedications([])
    setDynamicAnswer('')
    setCycleDay(0)
  }

  const knownFoodTriggers = profileData?.known_food_triggers ?? []
  const dynamicLabel = getDynamicLabel(
    analyzeState?.confirmed_triggers ?? [],
    analyzeState?.suspected_triggers ?? [],
  )

  // ── Render: Intake chat ────────────────────────────────────────────────────

  if (phase === 'intake-chat') {
    return (
      <div className="p-6 max-w-2xl mx-auto space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Log Entry</h1>
          <Button variant="outline" size="sm" onClick={resetForm}>
            Log another
          </Button>
        </div>

        {redFlag && (
          <div className="bg-destructive/10 border border-destructive/30 rounded-lg px-4 py-3 text-sm text-destructive">
            ⚠️ Red flag symptoms detected. Please consult a doctor.
          </div>
        )}
        {mohAlert && (
          <div className="bg-chart-2/10 border border-chart-2/30 rounded-lg px-4 py-3 text-sm">
            ⚠️ Medication overuse alert — too many triptan or NSAID days in the last 30 days.
          </div>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">🧠 Intake Agent</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {chatMessages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] rounded-xl px-4 py-2.5 text-sm leading-relaxed ${
                    msg.role === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-foreground'
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            {isReplying && (
              <div className="flex justify-start">
                <div className="bg-muted rounded-xl px-4 py-2.5 text-sm text-muted-foreground">
                  Thinking…
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </CardContent>
        </Card>

        <div className="flex gap-2">
          <Input
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            placeholder="Reply to the intake agent…"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleChatReply()
              }
            }}
            disabled={isReplying}
          />
          <Button onClick={handleChatReply} disabled={isReplying || !chatInput.trim()}>
            Send
          </Button>
        </div>
      </div>
    )
  }

  // ── Render: Form ───────────────────────────────────────────────────────────

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-5">
      <h1 className="text-2xl font-bold">Log Entry</h1>

      {/* SOS pending banner */}
      {sosPending && (
        <div className="bg-destructive/10 border border-destructive/30 rounded-lg px-4 py-3 text-sm flex items-start justify-between gap-3">
          <span>
            🔴 Migraine logged for{' '}
            <strong>{sosPending.entry_date}</strong> — pain{' '}
            <strong>{sosPending.pain_level}/10</strong>. Add details when you feel up to it.
          </span>
          <button
            className="shrink-0 text-muted-foreground hover:text-foreground text-xs underline"
            onClick={() => {
              clearSosPending()
              setSosPending(null)
              setMigraineOccurred(false)
            }}
          >
            False alarm
          </button>
        </div>
      )}

      {submitError && (
        <div className="bg-destructive/10 border border-destructive/30 rounded-lg px-4 py-3 text-sm text-destructive">
          {submitError}
        </div>
      )}

      {/* Date + toggle — hidden when SOS pending (date is locked) */}
      {!sosPending && (
        <Card>
          <CardContent className="pt-4 space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="entry-date">Date</Label>
              <Input
                id="entry-date"
                type="date"
                value={entryDate}
                max={today}
                onChange={(e) => setEntryDate(e.target.value)}
                style={{ colorScheme: 'dark' }}
              />
            </div>

            <div className="flex items-center justify-between">
              <Label htmlFor="migraine-toggle" className="text-sm cursor-pointer">
                Did you have a migraine today?
              </Label>
              <button
                id="migraine-toggle"
                role="switch"
                aria-checked={migraineOccurred}
                onClick={() => setMigraineOccurred((v) => !v)}
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                  migraineOccurred ? 'bg-destructive' : 'bg-muted'
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-lg ring-0 transition-transform ${
                    migraineOccurred ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Migraine-free quick form ── */}
      {!migraineOccurred && (
        <>
          <p className="text-sm text-muted-foreground px-1">✅ Great day — 30-second check-in</p>

          <Card>
            <CardContent className="pt-4 space-y-6">
              <SliderField
                label="Sleep quality last night"
                value={sleepQuality}
                onChange={setSleepQuality}
                hint="/10"
              />
              <SliderField
                label="Stress level today"
                value={stressLevel}
                onChange={setStressLevel}
                hint="/10"
              />

              {knownFoodTriggers.length > 0 && (
                <div className="space-y-2">
                  <Label className="text-sm">Any of your trigger foods today?</Label>
                  <PillToggle
                    options={knownFoodTriggers}
                    selected={selectedFoods}
                    onChange={setSelectedFoods}
                  />
                </div>
              )}

              <div className="space-y-2">
                <Label className="text-sm">Hydration today</Label>
                <RadioPills
                  options={['good', 'average', 'low']}
                  value={hydrationChoice}
                  onChange={(v) => setHydrationChoice(v as 'good' | 'average' | 'low')}
                  labels={{ good: '👍 Good', average: '😐 Average', low: '👎 Low' }}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="free-notes" className="text-sm">
                  Anything notable? <span className="text-muted-foreground">(optional)</span>
                </Label>
                <textarea
                  id="free-notes"
                  value={freeNotes}
                  onChange={(e) => setFreeNotes(e.target.value)}
                  placeholder="Stress source, unusual food, fragrance, anything..."
                  rows={2}
                  className="w-full bg-input/30 border border-input rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground resize-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:border-ring"
                />
              </div>

              <Button
                className="w-full"
                onClick={submitFreeDay}
                disabled={isSubmitting}
              >
                {isSubmitting ? 'Saving…' : '💾 Save'}
              </Button>
            </CardContent>
          </Card>
        </>
      )}

      {/* ── SOS quick capture (today, no pending) ── */}
      {migraineOccurred && !isPast && !sosPending && (
        <>
          <p className="text-sm text-muted-foreground px-1">
            🔴 Quick capture now — add the details when you recover.
          </p>

          <Card>
            <CardContent className="pt-4 space-y-6">
              <SliderField
                label="Pain level right now"
                value={sosQuickPain}
                onChange={setSosQuickPain}
                hint="/10"
              />

              <div className="space-y-2">
                <Label className="text-sm">Medication taken?</Label>
                <RadioPills
                  options={SOS_QUICK_MEDS}
                  value={sosQuickMed}
                  onChange={setSosQuickMed}
                />
              </div>

              {submitError && (
                <p className="text-sm text-destructive">{submitError}</p>
              )}

              <Button
                className="w-full"
                onClick={submitSosQuick}
                disabled={isSubmitting}
              >
                🆘 Log Now — I&apos;ll add details later
              </Button>
            </CardContent>
          </Card>
        </>
      )}

      {/* ── SOS detailed form ── */}
      {showDetailed && (
        <>
          {/* Auto-derived context panel */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium text-muted-foreground">
                📋 Pre-filled from your previous log — no need to re-enter
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                {[
                  { label: 'Sleep', value: autoSleepHours != null ? `${autoSleepHours}h` : '—' },
                  { label: 'Sleep quality', value: autoSleepQuality != null ? `${autoSleepQuality}/10` : '—' },
                  { label: 'Stress', value: autoStress != null ? `${autoStress}/10` : '—' },
                  { label: 'Hydration', value: autoHydrationOz != null ? `${Math.round(autoHydrationOz)} oz` : '—' },
                ].map(({ label, value }) => (
                  <div key={label} className="space-y-0.5">
                    <p className="text-xs text-muted-foreground">{label}</p>
                    <p className="text-sm font-medium tabular-nums">{value}</p>
                  </div>
                ))}
              </div>
              {autoFoods.length > 0 && (
                <p className="mt-2 text-xs text-muted-foreground">
                  Foods logged: {autoFoods.join(', ')}
                </p>
              )}
            </CardContent>
          </Card>

          {/* Q1: Prodrome */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">1. Any warning signs before it hit?</CardTitle>
            </CardHeader>
            <CardContent>
              <PillToggle
                options={PRODROME_OPTIONS}
                selected={prodromes}
                onChange={setProdromes}
              />
            </CardContent>
          </Card>

          {/* Q2: Pain details */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">2. Pain: where and how long?</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <SliderField
                label="Pain level"
                value={detailPainLevel}
                onChange={setDetailPainLevel}
                hint="/10"
              />

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label className="text-sm">Location</Label>
                  <select
                    value={painLocation}
                    onChange={(e) => setPainLocation(e.target.value)}
                    className="w-full h-8 bg-input/30 border border-input rounded-lg px-2.5 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
                    style={{ colorScheme: 'dark' }}
                  >
                    <option value="">— select —</option>
                    {PAIN_LOCATIONS.map((loc) => (
                      <option key={loc} value={loc}>
                        {loc.replaceAll('_', ' ')}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1.5">
                  <Label className="text-sm">Duration (hours)</Label>
                  <Input
                    type="number"
                    min={0}
                    max={72}
                    step={0.5}
                    value={durationHours || ''}
                    onChange={(e) => setDurationHours(Number(e.target.value))}
                    placeholder="e.g. 4"
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Q3: Relief */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">3. What helped?</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <PillToggle
                options={RELIEF_METHODS}
                selected={reliefMethods}
                onChange={setReliefMethods}
              />
              {reliefMethods.length > 0 && (
                <SliderField
                  label="How effective overall?"
                  value={reliefEffectiveness}
                  onChange={setReliefEffectiveness}
                  hint="/10"
                />
              )}
            </CardContent>
          </Card>

          {/* Medications */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Medications taken</CardTitle>
            </CardHeader>
            <CardContent>
              <PillToggle
                options={ALL_MEDICATIONS}
                selected={medications}
                onChange={setMedications}
              />
            </CardContent>
          </Card>

          {/* Q4: Dynamic trigger question */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">4. {dynamicLabel}</CardTitle>
            </CardHeader>
            <CardContent>
              <Input
                value={dynamicAnswer}
                onChange={(e) => setDynamicAnswer(e.target.value)}
                placeholder="Type your answer here..."
              />
            </CardContent>
          </Card>

          {/* Cycle day (conditional) */}
          {showsCycleDay(profileData?.hormonal_status) && (
            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center gap-4">
                  <Label htmlFor="cycle-day" className="text-sm shrink-0">
                    Cycle day{' '}
                    <span className="text-muted-foreground">(optional)</span>
                  </Label>
                  <Input
                    id="cycle-day"
                    type="number"
                    min={0}
                    max={35}
                    value={cycleDay || ''}
                    onChange={(e) => setCycleDay(Number(e.target.value))}
                    placeholder="e.g. 14"
                    className="max-w-24"
                  />
                </div>
              </CardContent>
            </Card>
          )}

          <Button
            className="w-full"
            onClick={submitDetailed}
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Saving…' : '💾 Submit'}
          </Button>
        </>
      )}
    </div>
  )
}