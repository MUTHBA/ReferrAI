// Status chip: full pill, tinted by tone. Tones follow DESIGN.md
// (jade = approved/active/paid, amber = pending, rose = rejected/fraud,
// grey = dismissed/inactive, cobalt = AI / informational).
import { cn } from '@/lib/utils'

const TONES = {
  jade: 'bg-jade-soft text-jade',
  amber: 'bg-amber-soft text-amber',
  rose: 'bg-rose-soft text-rose',
  cobalt: 'bg-cobalt-soft text-cobalt',
  grey: 'bg-muted text-muted-text',
}

export function Pill({ tone = 'grey', className, children, dot = false }) {
  return (
    <span
      className={cn(
        'inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 text-label font-medium',
        TONES[tone],
        className,
      )}
    >
      {dot && <span className="size-1.5 rounded-full bg-current" aria-hidden />}
      {children}
    </span>
  )
}

// Status vocabularies per record type -> [label, tone].
const STATUS = {
  withdrawal: {
    pending: ['Pending review', 'amber'],
    approved: ['Approved', 'jade'],
    paid: ['Paid', 'jade'],
    rejected: ['Rejected', 'rose'],
  },
  commission: {
    pending: ['Pending', 'amber'],
    approved: ['Earned', 'jade'],
    paid: ['Paid', 'jade'],
    reversed: ['Reversed', 'rose'],
  },
  partner: {
    active: ['Active', 'jade'],
    pending: ['Pending', 'amber'],
    suspended: ['Suspended', 'rose'],
  },
  fraud: {
    pending_review: ['Pending review', 'amber'],
    confirmed: ['Confirmed fraud', 'rose'],
    dismissed: ['Dismissed', 'grey'],
  },
  candidate: {
    new: ['New', 'cobalt'],
    reviewed: ['Reviewed', 'grey'],
    invited: ['Invited', 'jade'],
    dismissed: ['Dismissed', 'grey'],
  },
  link: {
    true: ['Active', 'jade'],
    false: ['Inactive', 'grey'],
  },
}

export function StatusPill({ kind, status, className }) {
  const [label, tone] = STATUS[kind]?.[String(status)] || [status ? String(status).replace(/_/g, ' ') : '—', 'grey']
  return (
    <Pill tone={tone} className={className}>
      {label}
    </Pill>
  )
}
