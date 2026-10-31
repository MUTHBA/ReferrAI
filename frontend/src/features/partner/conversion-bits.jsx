// Pieces shared by the conversions tables (partner pages and admin partner detail).
import { ScoreBadge } from '@/components/app/ScoreBadge'

export function attributionLabel(conv) {
  if (conv.via_code) return 'Code'
  return conv.attribution_model === 'first_click' ? 'First click' : 'Last click'
}

export function QualityCell({ conv }) {
  // No status yet = the background scoring task hasn't finished.
  return <ScoreBadge score={conv.quality_score} status={conv.quality_status} pendingLabel="Scoring…" />
}

export function sourceLabel(source) {
  if (!source) return 'Direct'
  return source.charAt(0).toUpperCase() + source.slice(1)
}

export function deviceLabel(device) {
  if (!device) return '—'
  return { mobile: 'Mobile', desktop: 'Desktop', tablet: 'Tablet', bot: 'Bot' }[device] || device
}
