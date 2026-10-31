// -----------------------------------------------------------------------------
// Partner dashboard: ledger strip (wallet, earnings, conversions, clicks for
// the chosen range), earnings chart, tier progress, AI scores, and the latest
// conversions.
// -----------------------------------------------------------------------------

import { useQuery } from '@tanstack/react-query'
import { ArrowRight } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { LedgerStrip } from '@/components/app/LedgerStrip'
import { PageHeader } from '@/components/app/PageHeader'
import { RangeSwitch } from '@/components/app/RangeSwitch'
import { ScoreBadge } from '@/components/app/ScoreBadge'
import { EmptyState, ErrorState, LoadingRows } from '@/components/app/States'
import { compactMoney, TimeChart } from '@/components/app/TimeChart'
import { Button } from '@/components/ui/button'
import { Panel, PanelBody, PanelHeader } from '@/components/ui/panel'
import { Table, TableWrap, Td, Th, THead, Tr } from '@/components/ui/table'
import { partnerApi } from '@/lib/endpoints'
import { date, money, number, percent, signedMoney, toNumber } from '@/lib/format'

import { QualityCell } from './conversion-bits'
import { TierProgress } from './TierProgress'

function sum(list, key) {
  return (list || []).reduce((acc, p) => acc + (toNumber(p[key]) || 0), 0)
}

export default function DashboardPage() {
  const [days, setDays] = useState(30)
  const dash = useQuery({ queryKey: ['partner-dashboard', days], queryFn: () => partnerApi.dashboard(days) })
  const profile = useQuery({ queryKey: ['me', 'partner'], queryFn: partnerApi.profile })
  const recent = useQuery({ queryKey: ['conversions', 'recent'], queryFn: () => partnerApi.conversions({ limit: 5 }) })

  const d = dash.data
  const chart = d?.earnings_chart || []
  const clicks = sum(chart, 'clicks')
  const conversions = sum(chart, 'conversions')
  const firstName = profile.data?.name?.split(' ')[0]

  return (
    <>
      <PageHeader
        title={firstName ? `Welcome back, ${firstName}` : 'Dashboard'}
        description="Your referrals, earnings and tier at a glance."
        actions={<RangeSwitch value={days} onChange={setDays} />}
      />

      {dash.isError ? (
        <Panel className="mb-6">
          <ErrorState error={dash.error} onRetry={dash.refetch} />
        </Panel>
      ) : (
        <LedgerStrip
          loading={dash.isLoading}
          items={[
            {
              label: 'Wallet balance',
              value: money(d?.kpis.wallet_balance),
              tone: 'jade',
              context: toNumber(d?.kpis.pending_withdrawals) > 0 ? `${money(d.kpis.pending_withdrawals)} waiting for payout` : 'Ready to withdraw',
            },
            { label: `Earned, last ${days} days`, value: money(sum(chart, 'earnings')), context: `${money(d?.kpis.total_earnings)} all time` },
            { label: `Conversions, last ${days} days`, value: number(conversions), context: `${number(d?.kpis.conversion_count)} all time` },
            {
              label: `Clicks, last ${days} days`,
              value: number(clicks),
              context: clicks ? `${percent(conversions / clicks)} converted` : 'No clicks yet',
            },
          ]}
        />
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Panel>
          <PanelHeader title="Earnings" description={`Commission earned per day, last ${days} days`} />
          <PanelBody>
            {dash.isLoading ? (
              <LoadingRows rows={4} className="p-0" />
            ) : chart.length ? (
              <TimeChart
                data={chart}
                series={[{ key: 'earnings', label: 'Earnings', color: 'var(--chart-1)' }]}
                format={(v) => money(v)}
                axisFormat={compactMoney}
                height={260}
              />
            ) : (
              <EmptyState title="No earnings yet">Your commission appears here every time a referred customer buys.</EmptyState>
            )}
          </PanelBody>
        </Panel>

        <div className="space-y-6">
          <Panel>
            <PanelHeader title="Your tier" />
            <PanelBody>{d ? <TierProgress tier={d.tier} compact /> : <LoadingRows rows={2} className="p-0" />}</PanelBody>
          </Panel>
          <Panel>
            <PanelHeader title="Your AI scores" description="Updated automatically every day." />
            <PanelBody className="space-y-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-body font-medium text-text">Partner rank</div>
                  <div className="text-label text-muted-text">
                    {d?.rank_position ? `#${d.rank_position} of ${d.total_ranked_partners} partners` : 'Ranked after your first scoring run'}
                  </div>
                </div>
                <ScoreBadge score={d?.rank_score} />
              </div>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-body font-medium text-text">Referral quality</div>
                  <div className="text-label text-muted-text">Average across your sales</div>
                </div>
                <ScoreBadge score={d?.quality_score} pendingLabel="No sales scored yet" />
              </div>
            </PanelBody>
          </Panel>
        </div>
      </div>

      <Panel className="mt-6">
        <PanelHeader
          title="Recent conversions"
          actions={
            <Button asChild variant="ghost" size="sm">
              <Link to="/partner/conversions">
                View all <ArrowRight />
              </Link>
            </Button>
          }
        />
        {recent.isLoading ? (
          <LoadingRows rows={3} />
        ) : recent.isError ? (
          <ErrorState error={recent.error} onRetry={recent.refetch} />
        ) : !recent.data.length ? (
          <EmptyState title="No conversions yet">
            Share a referral link from the Referral links page. Sales you refer show up here.
          </EmptyState>
        ) : (
          <TableWrap>
            <Table>
              <THead>
                <tr>
                  <Th>Date</Th>
                  <Th>Order ID</Th>
                  <Th num>Order value</Th>
                  <Th>Quality</Th>
                  <Th num>Commission</Th>
                </tr>
              </THead>
              <tbody>
                {recent.data.map((c) => (
                  <Tr key={c.id}>
                    <Td className="whitespace-nowrap">{date(c.converted_at)}</Td>
                    <Td className="whitespace-nowrap font-medium">{c.external_reference}</Td>
                    <Td num>{money(c.conversion_value)}</Td>
                    <Td>
                      <QualityCell conv={c} />
                    </Td>
                    <Td num className={toNumber(c.commission_amount) > 0 ? 'font-semibold text-jade' : ''}>
                      {c.commission_amount ? signedMoney(c.commission_amount) : '—'}
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </TableWrap>
        )}
      </Panel>
    </>
  )
}
