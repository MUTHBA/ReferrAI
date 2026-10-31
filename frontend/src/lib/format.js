// -----------------------------------------------------------------------------
// frontend/src/lib/format.js
//
// Display formatting used everywhere, so money, dates and labels look the same
// on every page. The API sends money as decimal strings ("1240.50"); these
// helpers accept strings or numbers and show "—" for missing values.
//   money(1240.5)        -> "$1,240.50"
//   signedMoney(-25.2)   -> "−$25.20"
//   date("2026-10-19")   -> "19 Oct 2026"
//   dateTime(iso)        -> "19 Oct 2026, 14:32"
// -----------------------------------------------------------------------------

const MONEY = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
const MONEY_ROUND = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
const NUMBER = new Intl.NumberFormat('en-US')
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
// Fixed month names ("Sep", not the locale's "Sept"): "19 Oct 2026".
const DATE = { format: (d) => `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}` }
const SHORT_DATE = { format: (d) => `${d.getDate()} ${MONTHS[d.getMonth()]}` }
const TIME = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false })

export const DASH = '—'

export function toNumber(value) {
  if (value === null || value === undefined || value === '') return null
  const n = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(n) ? n : null
}

export function money(value, { round = false } = {}) {
  const n = toNumber(value)
  if (n === null) return DASH
  return (round ? MONEY_ROUND : MONEY).format(n)
}

/** "+$28.80" / "−$25.20" (true minus sign). */
export function signedMoney(value) {
  const n = toNumber(value)
  if (n === null) return DASH
  const text = MONEY.format(Math.abs(n))
  return n < 0 ? `−${text}` : `+${text}`
}

export function number(value) {
  const n = toNumber(value)
  return n === null ? DASH : NUMBER.format(n)
}

/** Fraction -> percent text: percent(0.125) -> "12.5%". */
export function percent(fraction, digits = 1) {
  const n = toNumber(fraction)
  if (n === null) return DASH
  const factor = 10 ** digits
  const value = Math.round(n * 100 * factor) / factor
  return `${Number.isInteger(value) ? value : value.toFixed(digits)}%`
}

function toDate(value) {
  if (!value) return null
  // Plain dates ("2026-10-19") are calendar days; don't shift them by time zone.
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [y, m, d] = value.split('-').map(Number)
    return new Date(y, m - 1, d)
  }
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? null : d
}

export function date(value) {
  const d = toDate(value)
  return d ? DATE.format(d) : DASH
}

export function shortDate(value) {
  const d = toDate(value)
  return d ? SHORT_DATE.format(d) : DASH
}

export function dateTime(value) {
  const d = toDate(value)
  return d ? `${DATE.format(d)}, ${TIME.format(d)}` : DASH
}

/** Whole days between a past date and now (0 for today). */
export function daysSince(value) {
  const d = toDate(value)
  if (!d) return null
  return Math.max(0, Math.floor((Date.now() - d.getTime()) / 86_400_000))
}

export function relativeDays(value) {
  const days = daysSince(value)
  if (days === null) return DASH
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  return `${days} days ago`
}

/** "pending_review" -> "Pending review". */
export function humanize(value) {
  if (!value) return DASH
  const text = String(value).replace(/[_.]/g, ' ').trim()
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** Commission rate label for a tier or setting: percentage stored as a fraction. */
export function rateLabel(type, value) {
  const n = toNumber(value)
  if (n === null) return DASH
  if (type === 'fixed') return `${money(n)} per sale`
  return percent(n)
}

export function initials(name) {
  if (!name) return '?'
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join('')
}
