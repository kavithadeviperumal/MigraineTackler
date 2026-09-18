'use client'

import { Label } from '@/components/ui/label'

// ── PillToggle — multi-select pill group ───────────────────────────────────────

export function PillToggle({
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

// ── RadioPills — single-select pill group ──────────────────────────────────────

export function RadioPills({
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

// ── SliderField — labeled range input ─────────────────────────────────────────

export function SliderField({
  label,
  value,
  min = 1,
  max = 10,
  step = 1,
  onChange,
  hint,
  formatValue,
}: {
  label: string
  value: number
  min?: number
  max?: number
  step?: number
  onChange: (v: number) => void
  hint?: string
  formatValue?: (v: number) => string
}) {
  const display = formatValue ? formatValue(value) : `${value}${hint ?? ''}`
  return (
    <div className="space-y-2">
      <div className="flex justify-between items-baseline">
        <Label className="text-sm">{label}</Label>
        <span className="text-sm font-semibold tabular-nums text-primary">{display}</span>
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

// ── TimeInput — styled time picker ────────────────────────────────────────────

export function TimeInput({
  id,
  label,
  value,
  onChange,
}: {
  id: string
  label: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="text-sm">
        {label}
      </Label>
      <input
        id={id}
        type="time"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full h-8 bg-input/30 border border-input rounded-lg px-2.5 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:border-ring"
        style={{ colorScheme: 'dark' }}
      />
    </div>
  )
}