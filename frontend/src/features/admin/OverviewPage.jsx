// -----------------------------------------------------------------------------
// Admin overview: period figures (ledger strip), revenue/commission and
// clicks/conversions charts (separate charts — different units never share
// an axis), what needs attention, top partners, and CSV exports.
// -----------------------------------------------------------------------------

import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Download } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { LedgerStrip } from '@/components/app/LedgerStrip'
import { PageHeader } from '@/components/app/PageHeader'
import { RangeSwitch } from '@/components/app/RangeSwitch'
import { ScoreBadge } from '@/components/app/ScoreBadge'
import { EmptyState, ErrorState, LoadingRows } from '@/components/app/States'
import { compactMoney, compactNumber, TimeChart } from '@/components/app/TimeChart'
import { Button } from '@/components/ui/button'
import { Panel, PanelBody, PanelHeader } from '@/components/ui/panel'
import { Select } from '@/components/ui/select'
import { Table, TableWrap, Td, Th, THead, Tr } from '@/components/ui/table'
import { errorMessage } from '@/lib/api'
import { adminApi, downloadReport } from '@/lib/endpoints'
import { money, number, percent, relativeDays, toNumber } from '@/lib/format'

function ExportMenu() {
  const [busy, setBusy] = useState(false)
  async function run(name) {
    if (!name) return
    setBusy(true)
    try {
      await downloadReport(name)
    } catch (e) {
      toast.error(errorMessage(e, 'The export failed.'))
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="flex items-center gap-2">
      <Download className="size-4 text-muted-text" aria-hidden />
      <Select aria-label="Export CSV" value="" onChange={(e) => run(e.target.value)} disabled={busy} className="w-44">
        <option value="">Export CSV…</option>
        <option value="referrals">Conversions</option>
        <option value="commissions">Commissions</option>
        <option value="partners">Partners</option>
      </Select>
    </div>
  )
}

function AttentionItem({ tone, title, detail, to, action }) {
  const dot = { rose: 'bg-rose', amber: 'bg-amber', cobalt: 'bg-cobalt' }[tone]
  return (
    <li className="flex items-start gap-3 py-3">
      <span className={`mt-1.5 size-2 shrink-0 rounded-full ${dot}`} aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="text-body font-medium text-text">{title}</div>
        {detail && <div className="text-caption text-muted-text">{detail}</div>}
      </div>
      <Button asChild variant="ghost" size="sm">
        <Link to={to}>{action}</Link>
      </Button>
    </li>
  )
}

export default function OverviewPage() {
  const [days, setDays] = useState(30)
  const dash = useQuery({ queryKey: ['admin-dashboard', days], queryFn: () => adminApi.dashboard(days) })
  const d = dash.data
  const k = d?.kpis

  const attention = []
  if (k?.fraud_alert_count)
    attention.push({
      tone: 'rose',
      title: `${number(k.fraud_alert_count)} fraud ${k.fraud_alert_count === 1 ? 'alert' : 'alerts'} waiting for review`,
      detail: d.recent_fraud_flags[0] ? `Latest: ${d.recent_fraud_flags[0].partner_name}, ${relativeDays(d.recent_fraud_flags[0].created_at).toLowerCase()}` : null,
      to: '/admin/fraud',
      action: 'Review',
    })
  if (k?.pending_payout_count)
    attention.push({
      tone: 'amber',
      title: `${number(k.pending_payout_count)} ${k.pending_payout_count === 1 ? 'payout' : 'payouts'} waiting for approval`,
      detail: `${money(k.pending_payout_amount)} in total`,
      to: '/admin/payouts',
      action: 'Open',
    })
  if (k?.churn_alert_count)
    attention.push({
      tone: 'cobalt',
      title: `${number(k.churn_alert_count)} ${k.churn_alert_count === 1 ? 'partner' : 'partners'} at risk of churning`,
      detail: d.churn_at_risk_partners.slice(0, 3).map((p) => p.name).join(', '),
      to: '/admin/churn',
      action: 'View',
    })

  return (
    <>
      <PageHeader
        title="Overview"
        description="Referral revenue, commissions and what needs your attention."
        actions={
          <>
            <RangeSwitch value={days} onChange={setDays} />
            <ExportMenu />
          </>
        }
      />

      {dash.isError ? (
        <Panel>
          <ErrorState error={dash.error} onRetry={dash.refetch} />
        </Panel>
      ) : (
        <>
          <LedgerStrip
            loading={dash.isLoading}
            items={[
              { label: 'Revenue referred', value: money(k?.period_revenue, { round: true }), context: `Last ${days} days · ${money(k?.total_revenue, { round: true })} all time` },
              {
                label: 'Commission earned',
                value: money(k?.period_commission, { round: true }),
                context: toNumber(k?.period_revenue) ? `${percent(toNumber(k.period_commission) / toNumber(k.period_revenue))} of revenue` : `Last ${days} days`,
              },
              {
                label: 'Pending payouts',
                value: money(k?.pending_payout_amount),
                tone: k?.pending_payout_count ? 'amber' : 'default',
                context: `${number(k?.pending_payout_count)} ${k?.pending_payout_count === 1 ? 'request' : 'requests'} to review`,
              },
              {
                label: 'Open fraud alerts',
                value: number(k?.fraud_alert_count),
                tone: k?.fraud_alert_count ? 'rose' : 'default',
                context: 'Pending review',
              },
              { label: 'Partners at churn risk', value: number(k?.churn_alert_count), context: `${number(k?.active_partners)} active partners` },
            ]}
          />

          <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
            <div className="min-w-0 space-y-6">
              <Panel>
                <PanelHeader title="Revenue and commission" description={`Per day, last ${days} days`} />
                <PanelBody>
                  {dash.isLoading ? (
                    <LoadingRows rows={4} className="p-0" />
                  ) : (
                    <TimeChart
                      data={d.volume_chart}
                      series={[
                        { key: 'revenue', label: 'Revenue', color: 'var(--chart-1)' },
                        { key: 'commission', label: 'Commission', color: 'var(--chart-2)' },
                      ]}
                      format={(v) => money(v)}
                      axisFormat={compactMoney}
                    />
                  )}
                </PanelBody>
              </Panel>
              <div className="grid gap-6 md:grid-cols-2">
                <Panel>
                  <PanelHeader
                    title="Clicks"
                    description={`${number(k?.period_clicks)} in the last ${days} days`}
                  />
                  <PanelBody>
                    {dash.isLoading ? (
                      <LoadingRows rows={3} className="p-0" />
                    ) : (
                      <TimeChart data={d.volume_chart} series={[{ key: 'clicks', label: 'Clicks', color: 'var(--chart-2)' }]} kind="bar" format={number} axisFormat={compactNumber} height={180} />
                    )}
                  </PanelBody>
                </Panel>
                <Panel>
                  <PanelHeader
                    title="Conversions"
                    description={`${number(k?.period_conversions)} sales · ${k?.conversion_rate !== null && k?.conversion_rate !== undefined ? `${percent(k.conversion_rate)} of clicks` : 'no clicks yet'}`}
                  />
                  <PanelBody>
                    {dash.isLoading ? (
                      <LoadingRows rows={3} className="p-0" />
                    ) : (
                      <TimeChart data={d.volume_chart} series={[{ key: 'conversions', label: 'Conversions', color: 'var(--chart-1)' }]} kind="bar" format={number} axisFormat={compactNumber} height={180} />
                    )}
                  </PanelBody>
                </Panel>
              </div>
            </div>

            <div className="min-w-0 space-y-6">
              <Panel>
                <PanelHeader title="Needs attention" />
                <PanelBody className="py-1">
                  {dash.isLoading ? (
                    <LoadingRows rows={3} className="px-0" />
                  ) : attention.length ? (
                    <ul className="divide-y divide-line">
                      {attention.map((a) => (
                        <AttentionItem key={a.to} {...a} />
                      ))}
                    </ul>
                  ) : (
                    <EmptyState title="All clear">No fraud alerts, payouts or churn risks waiting.</EmptyState>
                  )}
                </PanelBody>
              </Panel>

              <Panel>
                <PanelHeader
                  title="Top partners"
                  description="By revenue referred"
                  actions={
                    <Button asChild variant="ghost" size="sm">
                      <Link to="/admin/ranking">
                        Ranking <ArrowRight />
                      </Link>
                    </Button>
                  }
                />
                {dash.isLoading ? (
                  <LoadingRows rows={4} />
                ) : !d.top_partners.length ? (
                  <EmptyState>Partners appear here once they make sales.</EmptyState>
                ) : (
                  <TableWrap>
                    <Table>
                      <THead>
                        <tr>
                          <Th>Partner</Th>
                          <Th num>Sales</Th>
                          <Th num>Revenue</Th>
                          <Th>Rank</Th>
                        </tr>
                      </THead>
                      <tbody>
                        {d.top_partners.map((p) => (
                          <Tr key={p.partner_id}>
                            <Td className="max-w-[160px]">
                              <Link to={`/admin/partners/${p.partner_id}`} className="block truncate font-medium hover:underline">
                                {p.name}
                              </Link>
                              <span className="text-label text-muted-text">{p.tier_name || 'No tier'}</span>
                            </Td>
                            <Td num>{number(p.conversions)}</Td>
                            <Td num>{money(p.revenue, { round: true })}</Td>
                            <Td>
                              <ScoreBadge score={p.rank_score} pendingLabel="—" />
                            </Td>
                          </Tr>
                        ))}
                      </tbody>
                    </Table>
                  </TableWrap>
                )}
              </Panel>
            </div>
          </div>
        </>
      )}
    </>
  )
}
