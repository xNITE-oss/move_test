// API'ga so'rov. SSR paytida to'liq manzil (movespace.uz), brauzerda /api
// (dev'da proxy, prod'da bir xil domen).
export function apiUrl(path: string): string {
  const config = useRuntimeConfig()
  if (import.meta.server) {
    return `${config.apiBase}${path}`
  }
  return `${config.public.apiBase}${path.replace(/^\/api/, '')}`
}

const UZ_MONTHS = [
  'yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun',
  'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr',
]

// Sanani o'zbekcha ko'rsatadi: "21 avgust" yoki "21 avgust 2026".
export function uzDate(iso?: string | null, withYear = false): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso.slice(0, 10)
  return `${d.getDate()} ${UZ_MONTHS[d.getMonth()]}${withYear ? ' ' + d.getFullYear() : ''}`
}

export interface SitePost {
  slug: string
  run_id: string
  rubric: string | null
  title: string
  lead: string
  tags: string[]
  reading_minutes: number
  published_at: string | null
}

export interface SitePostDetail extends SitePost {
  html: string
  body: string[]
  takeaway: string
  cta: string
}
