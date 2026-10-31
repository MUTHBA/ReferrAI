// -----------------------------------------------------------------------------
// Churn risk: partners likely to stop referring in the next 30 days, with the
// "why" bars behind each score. Partners under 30 days old aren't scored yet
// (the model needs history) and are listed separately with their progress.
// -----------------------------------------------------------------------------

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Mail, Play } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { LedgerStrip } from '@/components/app/LedgerStrip'
import { PageHeader } from '@/components/app/PageHeader'
import { ScoreBadge } from '@/components/app/ScoreBadge'
import { EmptyState, ErrorState, LoadingRows } from '@/components/app/States'
import { topFactors, WhyBars } from '@/components/app/WhyBars'
import { Button } from '@/components/ui/button'
import { Panel, PanelHeader } from '@/components/ui/panel'
import { Pill } from '@/components/ui/pill'
import { Spinner } from '@/components/ui/spinner'
import { Table, TableWrap, Td, Th, THead, Tr } from '@/components/ui/table'
import { errorMessage } from '@/lib/api'
import { adminApi } from '@/lib/endpoints'
import { date, daysSince, money, number, toNumber } from '@/lib/format'

function PartnerCell({ row }) {
  return (
    <div className="min-w-0">
      <Link to={`/admin/partners/${row.partner_id}`} className="block truncate font-semibold text-ink hover:underline">
        {row.name}
      </Link>
      <span className="block truncate text-label text-muted-text">{row.business_name || row.email}</span>
    </div>
  )
}

export default function ChurnRiskPage() {
  const qc = useQueryClient()
  const rows = useQuery({ queryKey: ['partner-scores', 'churn_risk'], queryFn: () => adminApi.partnerScores('churn_risk') })
  const settings = useQuery({ queryKey: ['settings'], queryFn: adminApi.settings })
  const [showAll, setShowAll] = useState(false)
  const run = useMutation({
    mutationFn: adminApi.runChurn,
    onSuccess: (r) => {
      toast.success(`Scored ${number(r.partners_scored)} partners.`)
      qc.invalidateQueries({ queryKey: ['partner-scores'] })
    },
    onError: (e) => toast.error(errorMessage(e)),
  })

  const threshold = toNumber(settings.data?.find((s) => s.key === 'churn.alert_threshold')?.value) ?? 65
  const all = (rows.data || []).filter((r) => r.status !== 'suspended')
  const atRisk = all.filter((r) => r.score !== null && r.score > threshold).sort((a, b) => b.score - a.score)
  const fine = all.filter((r) => r.score !== null && r.score <= threshold).sort((a, b) => b.score - a.score)
  const young = all.filter((r) => r.score_status === 'insufficient_data')
  const unscored = all.filter((r) => r.score === null && r.score_status !== 'insufficient_data')
  const revenueAtRisk = atRisk.reduce((a, r) => a + (toNumber(r.total_revenue) || 0), 0)
  const lastRun = (rows.data || []).map((r) => r.calculated_at).filter(Boolean).sort().pop()

  const riskTable = (list) => (
    <TableWrap>
      <Table>
        <THead>
          <tr>
            <Th>Partner</Th>
            <Th>Tier</Th>
            <Th>Churn risk</Th>
            <Th className="min-w-72">Why</Th>
            <Th>Last sale</Th>
            <Th>
              <span className="sr-only">Actions</span>
            </Th>
          </tr>
        </THead>
        <tbody>
          {list.map((r) => (
            <Tr key={r.partner_id}>
              <Td className="max-w-[200px]">
                <PartnerCell row={r} />
              </Td>
              <Td>{r.tier_name ? <Pill tone="grey">{r.tier_name}</Pill> : '—'}</Td>
              <Td>
                <ScoreBadge score={r.score} risk />
              </Td>
              <Td className="py-3">
                <WhyBars factors={topFactors(r.contributing_factors)} risk compact />
              </Td>
              <Td className="whitespace-nowrap">
                {r.last_conversion_at ? (
                  <>
                    {date(r.last_conversion_at)}
                    <span className="block text-label text-muted-text">{daysSince(r.last_conversion_at)} days ago</span>
                  </>
                ) : (
                  <span className="text-muted-text">No sales yet</span>
                )}
              </Td>
              <Td className="text-right whitespace-nowrap">
                <Button asChild variant="secondary" size="sm">
                  <a href={`mailto:${r.email}?subject=${encodeURIComponent('Checking in from ReferrAI')}`}>
                    <Mail />
                    Email
                  </a>
                </Button>
                <Button asChild variant="ghost" size="sm" className="ml-1">
                  <Link to={`/admin/partners/${r.partner_id}`}>
                    Open <ArrowRight />
                  </Link>
                </Button>
              </Td>
            </Tr>
          ))}
        </tbody>
      </Table>
    </TableWrap>
  )

  return (
    <>
      <PageHeader
        title="Churn risk"
        description="Partners likely to stop referring in the next 30 days."
        actions={
          <Button variant="secondary" onClick={() => run.mutate()} disabled={run.isPending}>
            {run.isPending ? <Spinner /> : <Play />}
            Score now
          </Button>
        }
      />
      <LedgerStrip
        loading={rows.isLoading || settings.isLoading}
        items={[
          { label: 'Alert threshold', value: `Above ${threshold}`, context: <Link to="/admin/settings" className="text-jade hover:underline">Change in settings</Link> },
          { label: 'Partners at risk', value: number(atRisk.length), tone: atRisk.length ? 'rose' : 'default', context: `of ${number(all.length - young.length - unscored.length)} scored` },
          { label: 'Revenue from them', value: money(revenueAtRisk, { round: true }), context: 'Referred all time' },
          { label: 'Last scored', value: lastRun ? date(lastRun) : '—', context: 'Runs automatically every day' },
        ]}
      />

      <Panel>
        <PanelHeader title="At risk" description={`Churn score above ${threshold}, highest first.`} />
        {rows.isLoading ? (
          <LoadingRows rows={5} />
        ) : rows.isError ? (
          <ErrorState error={rows.error} onRetry={rows.refetch} />
        ) : !atRisk.length ? (
          <EmptyState title="No partners at risk">Partners appear here when their churn score passes the threshold.</EmptyState>
        ) : (
          riskTable(atRisk)
        )}
      </Panel>

      {fine.length > 0 && (
        <Panel className="mt-6">
          <PanelHeader
            title="Everyone else"
            description={`${number(fine.length)} scored partners below the threshold.`}
            actions={
              <Button variant="ghost" size="sm" onClick={() => setShowAll((v) => !v)}>
                {showAll ? 'Hide' : 'Show'}
              </Button>
            }
          />
          {showAll && riskTable(fine)}
        </Panel>
      )}

      {(young.length > 0 || unscored.length > 0) && (
        <Panel className="mt-6">
          <PanelHeader title="Not enough history yet" description="Partners who joined less than 30 days ago aren't scored; the model needs 30 days of activity." />
          <TableWrap>
            <Table>
              <THead>
                <tr>
                  <Th>Partner</Th>
                  <Th>Joined</Th>
                  <Th num>Total sales</Th>
                  <Th>History</Th>
                </tr>
              </THead>
              <tbody>
                {[...young, ...unscored].map((r) => {
                  const days = Math.min(30, daysSince(r.joined_at) ?? 0)
                  return (
                    <Tr key={r.partner_id}>
                      <Td className="max-w-[240px]">
                        <PartnerCell row={r} />
                      </Td>
                      <Td className="whitespace-nowrap">{date(r.joined_at)}</Td>
                      <Td num>{number(r.total_conversions)}</Td>
                      <Td className="w-56">
                        {r.score_status === 'insufficient_data' || days < 30 ? (
                          <div className="flex items-center gap-3">
                            <div className="h-1.5 flex-1 rounded-full bg-muted" aria-hidden>
                              <div className="h-full rounded-full bg-cobalt" style={{ width: `${(days / 30) * 100}%` }} />
                            </div>
                            <span className="tabular text-label whitespace-nowrap text-muted-text">Day {days} of 30</span>
                          </div>
                        ) : (
                          <span className="text-label text-muted-text">Waiting for the next scoring run</span>
                        )}
                      </Td>
                    </Tr>
                  )
                })}
              </tbody>
            </Table>
          </TableWrap>
        </Panel>
      )}
    </>
  )
}
