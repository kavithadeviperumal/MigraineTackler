// ── Medications ────────────────────────────────────────────────────────────────

export const ALL_MEDICATIONS = [
  'acetaminophen',
  'acetaminophen + aspirin + caffeine',
  'almotriptan',
  'amitriptyline',
  'aspirin',
  'atenolol',
  'candesartan',
  'dihydroergotamine',
  'divalproex',
  'eletriptan',
  'eptinezumab',
  'erenumab',
  'ergotamine',
  'fremanezumab',
  'frovatriptan',
  'gabapentin',
  'galcanezumab',
  'ibuprofen',
  'lasmiditan',
  'lisinopril',
  'metoclopramide',
  'metoprolol',
  'naproxen',
  'naratriptan',
  'nortriptyline',
  'onabotulinumtoxinA',
  'ondansetron',
  'prochlorperazine',
  'promethazine',
  'propranolol',
  'rimegepant',
  'rizatriptan',
  'sumatriptan',
  'timolol',
  'topiramate',
  'ubrogepant',
  'valproate',
  'venlafaxine',
  'verapamil',
  'zavegepant',
  'zolmitriptan',
] as const

export const SOS_QUICK_MEDS = [
  'None yet',
  'acetaminophen',
  'ibuprofen',
  'rimegepant',
  'rizatriptan',
  'sumatriptan',
  'ubrogepant',
  'zolmitriptan',
  'other',
] as const

export const SUPPLEMENTS = [
  'butterbur',
  'CoQ10',
  'feverfew',
  'magnesium',
  'melatonin',
  'riboflavin_B2',
] as const

// ── Dietary triggers ───────────────────────────────────────────────────────────

export const ALL_FOODS = [
  'aged_cheese',
  'alcohol',
  'artificial_sweeteners',
  'avocado',
  'bananas',
  'beans_legumes',
  'beer',
  'caffeine',
  'chocolate',
  'citrus',
  'fermented_foods',
  'garlic',
  'gluten',
  'MSG',
  'nuts',
  'onions',
  'pickled_foods',
  'pizza',
  'processed_meat',
  'red_wine',
  'smoked_fish',
  'tyramine_rich_foods',
  'yeast_extract',
] as const

// ── Log entry options ──────────────────────────────────────────────────────────

export const PRODROME_OPTIONS = [
  'brain_fog',
  'fatigue',
  'food_cravings',
  'light_sensitivity',
  'mood_changes',
  'nausea',
  'neck_stiffness',
  'visual_aura',
  'yawning',
] as const

export const PAIN_LOCATIONS = [
  'behind_eye',
  'bilateral_temporal',
  'frontal',
  'full_head',
  'occipital',
  'temporal_left',
  'temporal_right',
] as const

export const RELIEF_METHODS = [
  'acupressure',
  'breathing_exercises',
  'caffeine',
  'cold_shower',
  'dark_room',
  'heat_pack',
  'hydration',
  'ice_pack',
  'lying_down',
  'meditation',
  'sleep',
  'vomiting_relief',
] as const

// ── Profile / settings ─────────────────────────────────────────────────────────

export const HORMONAL_STATUSES: Record<string, string> = {
  premenopausal_regular: 'Pre-menopausal — regular cycle',
  premenopausal_irregular: 'Pre-menopausal — irregular cycle',
  perimenopause: 'Perimenopause',
  postmenopausal: 'Post-menopausal',
  hormonal_contraception: 'On hormonal contraception (pill / patch / IUD / ring)',
  pregnant_postpartum: 'Pregnant or postpartum',
  not_applicable: 'Not applicable',
  prefer_not_to_say: 'Prefer not to say',
}

export const MIGRAINE_DURATIONS = [
  { value: '<1yr', label: 'Less than 1 year' },
  { value: '1-5yr', label: '1–5 years' },
  { value: '5+yr', label: 'More than 5 years' },
] as const

export const MIGRAINE_FREQUENCIES = [
  { value: '<1/month', label: 'Less than once a month' },
  { value: '1-3/month', label: '1–3 times a month' },
  { value: 'weekly', label: 'About once a week' },
  { value: 'daily', label: 'Multiple times a week or daily' },
] as const

export const JOB_TYPES = [
  { value: 'desk', label: 'Desk / sedentary' },
  { value: 'active', label: 'Mostly active / on feet' },
  { value: 'mixed', label: 'Mixed' },
] as const

// ── Caffeine ───────────────────────────────────────────────────────────────────

export const CAFFEINE_LEVELS = [
  { value: 'none', label: 'None' },
  { value: 'light', label: 'Light  (1–2 cups / <200 mg)' },
  { value: 'moderate', label: 'Moderate  (2–3 cups / 200–400 mg)' },
  { value: 'heavy', label: 'Heavy  (3+ cups / >400 mg)' },
] as const

export const CAFFEINE_MG: Record<string, number> = {
  none: 0,
  light: 100,
  moderate: 300,
  heavy: 500,
}

// ── Hydration ──────────────────────────────────────────────────────────────────

export const HYDRATION_MULT: Record<string, number> = {
  good: 1.2,
  average: 1.0,
  low: 0.55,
}

// ── Helpers ────────────────────────────────────────────────────────────────────

export function showsCycleDay(status: string | null | undefined): boolean {
  return ['premenopausal_regular', 'premenopausal_irregular', 'perimenopause'].includes(
    status ?? '',
  )
}

export function showsHormonalSection(status: string | null | undefined): boolean {
  return !['postmenopausal', 'not_applicable', 'prefer_not_to_say', null, undefined].includes(
    status as string,
  )
}