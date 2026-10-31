// -----------------------------------------------------------------------------
// Fraud alerts: raised when a click's fraud score (model + rules) is above the
// alert threshold — at most one open alert per partner per 24 hours. Admins
// confirm or dismiss. Nothing is suspended automatically; while an alert is
// open, the partner's withdrawals always need manual review.
// -----------------------------------------------------------------------------

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Clock, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { RulePills } from '@/components/app/ai-labels'
import { ConfirmDialog } from '@/components/app/ConfirmDialog'
import { PageHeader } from '@/components/app/PageHeader'
import { ScoreBadge } from '@/components/app/ScoreBadge'
import { EmptyState, ErrorState, LoadingRows } from '@/components/app/States'
import { topFactors, WhyBars } from '@/components/app/WhyBars'
import { Button } from '@/components/ui/button'
import { Panel } from '@/components/ui/panel'
import { StatusPill } from '@/components/ui/pill'
import { Segmented } from '@/components/ui/segmented'
import { adminApi } from '@/lib/endpoints'
import { dateTime } from '@/lib/format'

const TABS = [
  { value: 'pending_review', label: 'Pending review' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'dismissed', label: 'Dismissed' },
]

function AlertCard({ flag, onAction }) {
  const factors = flag.contributing_factors || {}
  const pending = flag.status === 'pending_review'
  return (
    <Panel className="grid gap-5 p-5 md:grid-cols-[220px_minmax(0,1fr)_auto]">
      <div className="min-w-0">
        <Link to={`/admin/partners/${flag.partner_id}`} className="block truncate text-body font-semibold text-ink hover:underline">
          {flag.partner_name}
        </Link>
        <div className="mt-1 flex items-center gap-1.5 text-caption text-muted-text">
          <Clock className="size-3.5" aria-hidden />
          {dateTime(flag.created_at)}
        </div>
        <div className="mt-3 flex items-center gap-2">
          <span className="text-caption text-muted-text">Fraud score</span>
          <ScoreBadge score={flag.score} risk outOf />
        </div>
        {!pending && (
          <div className="mt-3 space-y-1">
            <StatusPill kind="fraud" status={flag.status} />
            {flag.reviewed_at && <div className="text-label text-muted-text">Reviewed {dateTime(flag.reviewed_at)}</div>}
          </div>
        )}
      </div>
      <div className="min-w-0 space-y-3">
        <div className="text-label font-medium text-muted-text">Why it was flagged</div>
        <WhyBars factors={topFactors(factors)} risk emptyText={factors.ml_score === null ? 'Fraud model not trained; flagged by rules.' : 'No single model factor stood out.'} />
        <RulePills rules={factors.triggered_rules} />
      </div>
      <div className="flex flex-row flex-wrap gap-2 md:w-40 md:flex-col">
        {pending && (
          <>
            <Button variant="destructive" onClick={() => onAction('confirmed', flag)}>
              Confirm fraud
            </Button>
            <Button variant="secondary" onClick={() => onAction('dismissed', flag)}>
              Dismiss
            </Button>
          </>
        )}
        <Button asChild variant="ghost">
          <Link to={`/admin/partners/${flag.partner_id}`}>
            Open partner <ArrowRight />
          </Link>
        </Button>
      </div>
    </Panel>
  )
}

export default function FraudAlertsPage() {
  const qc = useQueryClient()
  const flags = useQuery({ queryKey: ['fraud-flags', 'all'], queryFn: () => adminApi.fraudFlags('all') })
  const [tab, setTab] = useState('pending_review')
  const [action, setAction] = useState(null)
  const all = flags.data || []
  const shown = all.filter((f) => f.status === tab).sort((a, b) => new Date(b.created_at) - new Date(a.created_at))

  async function review(notes) {
    await adminApi.reviewFraudFlag(action.flag.id, action.status, notes)
    toast.success(action.status === 'confirmed' ? `Marked ${action.flag.partner_name}'s alert as fraud.` : 'Alert dismissed.')
    qc.invalidateQueries({ queryKey: ['fraud-flags'] })
    qc.invalidateQueries({ queryKey: ['admin-dashboard'] })
    qc.invalidateQueries({ queryKey: ['withdrawals'] })
  }

  return (
    <>
      <PageHeader title="Fraud alerts" description="Alerts never suspend anyone automatically — you decide." />
      <Segmented
        className="mb-4"
        label="Alert status"
        value={tab}
        onChange={setTab}
        options={TABS.map((t) => ({ ...t, count: all.filter((f) => f.status === t.value).length }))}
      />
      {flags.isLoading ? (
        <Panel>
          <LoadingRows rows={6} />
        </Panel>
      ) : flags.isError ? (
        <Panel>
          <ErrorState error={flags.error} onRetry={flags.refetch} />
        </Panel>
      ) : !shown.length ? (
        <Panel>
          <EmptyState icon={ShieldCheck} title={tab === 'pending_review' ? 'No alerts waiting' : 'Nothing here'}>
            {tab === 'pending_review' ? 'New alerts appear here when traffic looks automated or suspicious.' : null}
          </EmptyState>
        </Panel>
      ) : (
        <div className="space-y-4">
          {shown.map((f) => (
            <AlertCard key={f.id} flag={f} onAction={(status, flag) => setAction({ status, flag })} />
          ))}
        </div>
      )}
      {action && (
        <ConfirmDialog
          key={`${action.status}-${action.flag.id}`}
          open
          onOpenChange={(v) => !v && setAction(null)}
          title={action.status === 'confirmed' ? `Confirm fraud for ${action.flag.partner_name}?` : 'Dismiss this alert?'}
          description={
            action.status === 'confirmed'
              ? 'This marks the alert as fraud. The account is not suspended automatically — suspend it from the partner page, and reverse affected commissions, if needed.'
              : 'The alert is closed as not fraud. Their withdrawals can be auto-approved again.'
          }
          confirmLabel={action.status === 'confirmed' ? 'Confirm fraud' : 'Dismiss alert'}
          destructive={action.status === 'confirmed'}
          reasonLabel="Notes (optional)"
          onConfirm={review}
        />
      )}
    </>
  )
}
