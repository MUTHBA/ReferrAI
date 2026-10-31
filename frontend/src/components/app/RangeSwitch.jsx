// Segmented 7/30/90-day range switch shared by dashboard charts (new in the frontend overhaul).

import { Segmented } from '@/components/ui/segmented'

const OPTIONS = [
  { value: 7, label: '7 days' },
  { value: 30, label: '30 days' },
  { value: 90, label: '90 days' },
]

export function RangeSwitch({ value, onChange }) {
  return <Segmented options={OPTIONS} value={value} onChange={onChange} label="Date range" size="sm" />
}
