// -----------------------------------------------------------------------------
// Admin partner detail: profile, money figures, the four AI scores with their
// explanations, recent conversions and withdrawals. Actions: change tier,
// suspend / reactivate (AI never suspends anyone — only an admin can).
// -----------------------------------------------------------------------------

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Ban, CircleCheck, SlidersHorizontal } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { RankBreakdown, RulePills } from '@/components/app/ai-labels'
import { ConfirmDialog } from '@/components/app/ConfirmDialog'
import { LedgerStrip } from '@/components/app/LedgerStrip'
import { PageHeader } from '@/components/app/PageHeader'
import { ScoreBadge } from '@/components/app/ScoreBadge'
import { EmptyState, ErrorState, LoadingRows } from '@/components/app/States'
import { topFactors, WhyBars } from '@/components/app/WhyBars'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Panel, PanelBody, PanelHeader } from '@/components/ui/panel'
import { Pill, StatusPill } from '@/components/ui/pill'
import { Select } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import { Table, TableWrap, Td, Th, THead, Tr } from '@/components/ui/table'
import { attributionLabel, QualityCell } from '@/features/partner/conversion-bits'
import { TierProgress } from '@/features/partner/TierProgress'
import { errorMessage } from '@/lib/api'
import { adminApi } from '@/lib/endpoints'
import { date, dateTime, money, number, rateLabel, toNumber } from '@/lib/format'

function ScorePanel({ title, subtitle, score, children, loading }) {
  return (
    <Panel>
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1 px-5 pt-4">
        <div className="min-w-[7.5rem]">
          <h2 className="text-body font-semibold text-ink">{title}</h2>
          {subtitle && <p className="text-label text-muted-text">{subtitle}</p>}
        </div>
        {!loading && score}
      </div>
      <div className="px-5 pt-3 pb-5">{loading ? <LoadingRows rows={2} className="p-0" /> : children}</div>
    </Panel>
  )
}

function TierDialog({ open, onOpenChange, partner, tiers }) {
  const qc = useQueryClient()
  const [tierId, setTierId] = useState(partner.tier_id || '')
  const save = useMutation({
    mutationFn: () => adminApi.updatePartner(partner.id, { tier_id: tierId }),
    onSuccess: (p) => {
      qc.invalidateQueries({ queryKey: ['partner', partner.id] })
      qc.invalidateQueries({ queryKey: ['partners'] })
      toast.success(`${p.name} moved to ${p.tier_name}.`)
      onOpenChange(false)
    },
  })
  return (
    <Dialog open={open} onOpenChange={(v) => (save.reset(), onOpenChange(v))}>
      <DialogContent title={`Change tier for ${partner.name}`} description="The new rate applies to future sales only. Past commissions don't change.">
        <Label htmlFor="tier-select">Tier</Label>
        <Select id="tier-select" className="mt-1.5" value={tierId} onChange={(e) => setTierId(e.target.value)}>
          {[...tiers].sort((a, b) => a.rank_order - b.rank_order).map((t) => (
            <option key={t.id} value={t.id}>
              {t.name} · {rateLabel(t.commission_type, t.commission_value)}
            </option>
          ))}
        </Select>
        {save.isError && (
          <Alert variant="error" className="mt-4">
            {errorMessage(save.error)}
          </Alert>
        )}
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={() => save.mutate()} disabled={!tierId || tierId === partner.tier_id || save.isPending}>
            {save.isPending && <Spinner />}
            Save tier
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function PartnerDetailPage() {
  const { partnerId } = useParams()
  const qc = useQueryClient()
  const partner = useQuery({ queryKey: ['partner', partnerId], queryFn: () => adminApi.partner(partnerId) })
  const dash = useQuery({ queryKey: ['partner', partnerId, 'dashboard'], queryFn: () => adminApi.partnerDashboard(partnerId, 30) })
  const conversions = useQuery({ queryKey: ['partner', partnerId, 'conversions'], queryFn: () => adminApi.partnerConversions(partnerId, { limit: 8 }) })
  const withdrawals = useQuery({ queryKey: ['withdrawals', { partner_id: partnerId }], queryFn: () => adminApi.withdrawals({ partner_id: partnerId }) })
  const churn = useQuery({ queryKey: ['score', partnerId, 'churn_risk'], queryFn: () => adminApi.score(partnerId, 'churn_risk') })
  const fraud = useQuery({ queryKey: ['score', partnerId, 'fraud_risk'], queryFn: () => adminApi.score(partnerId, 'fraud_risk') })
  const rank = useQuery({ queryKey: ['score', partnerId, 'ranking'], queryFn: () => adminApi.score(partnerId, 'ranking') })
  const tiers = useQuery({ queryKey: ['tiers'], queryFn: adminApi.tiers })
  const [tierOpen, setTierOpen] = useState(false)
  const [statusOpen, setStatusOpen] = useState(false)

  if (partner.isError) {
    return (
      <Panel>
        <ErrorState error={partner.error} onRetry={partner.refetch} />
      </Panel>
    )
  }
  const p = partner.data
  const k = dash.data?.kpis
  const clicks30 = (dash.data?.earnings_chart || []).reduce((a, x) => a + x.clicks, 0)
  const suspended = p?.status === 'suspended'

  async function toggleStatus() {
    const next = suspended ? 'active' : 'suspended'
    await adminApi.updatePartner(p.id, { status: next })
    qc.invalidateQueries({ queryKey: ['partner', p.id] })
    qc.invalidateQueries({ queryKey: ['partners'] })
    toast.success(next === 'suspended' ? `${p.name} is suspended.` : `${p.name} is active again.`)
  }

  return (
    <>
      <Link to="/admin/partners" className="mb-3 inline-flex items-center gap-1.5 text-caption text-muted-text hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden />
        Partners
      </Link>
      <PageHeader
        title={p ? p.name : 'Partner'}
        actions={
          p && (
            <>
              <Button variant="secondary" onClick={() => setTierOpen(true)} disabled={!tiers.data}>
                <SlidersHorizontal />
                Change tier
              </Button>
              {suspended ? (
                <Button onClick={() => setStatusOpen(true)}>
                  <CircleCheck />
                  Reactivate
                </Button>
              ) : (
                <Button variant="destructive" onClick={() => setStatusOpen(true)}>
                  <Ban />
                  Suspend partner
                </Button>
              )}
            </>
          )
        }
      >
        {p && (
          <div className="mb-1 flex flex-wrap items-center gap-2 text-caption text-muted-text">
            <span>{p.email}</span>
            {p.business_name && <span>· {p.business_name}</span>}
            {p.tier_name && <Pill tone="cobalt">{p.tier_name}</Pill>}
            <StatusPill kind="partner" status={p.status} />
            <span>· Joined {date(p.created_at)}</span>
          </div>
        )}
      </PageHeader>

      <LedgerStrip
        loading={partner.isLoading || dash.isLoading}
        items={[
          { label: 'Revenue referred', value: money(p?.total_revenue_contribution), context: 'All time' },
          { label: 'Commission earned', value: money(k?.total_earnings), context: `${money(k?.total_withdrawn)} withdrawn` },
          { label: 'Wallet balance', value: money(k?.wallet_balance), tone: 'jade', context: toNumber(k?.pending_withdrawals) ? `${money(k.pending_withdrawals)} waiting for payout` : 'No pending withdrawals' },
          { label: 'Sales', value: number(k?.conversion_count), context: `${number(k?.link_count)} links · ${number(k?.code_count)} codes` },
          { label: 'Clicks, last 30 days', value: number(clicks30), context: `${number(k?.click_count)} all time` },
        ]}
      />

      <div className="mb-6 grid gap-6 md:grid-cols-2 xl:grid-cols-4">
        <ScorePanel
          title="Rank"
          subtitle={dash.data?.rank_position ? `#${dash.data.rank_position} of ${dash.data.total_ranked_partners}` : 'Partner ranking score'}
          score={<ScoreBadge score={rank.data?.score} status={rank.data?.status} />}
          loading={rank.isLoading}
        >
          <RankBreakdown factors={rank.data?.contributing_factors} compact />
        </ScorePanel>
        <ScorePanel
          title="Churn risk"
          subtitle="Chance they stop referring"
          score={<ScoreBadge score={churn.data?.score} status={churn.data?.status} risk />}
          loading={churn.isLoading}
        >
          {churn.data?.score !== null && churn.data?.score !== undefined ? (
            <WhyBars factors={topFactors(churn.data.contributing_factors)} risk compact />
          ) : (
            <p className="text-caption text-muted-text">
              {churn.data?.status === 'insufficient_data' ? 'Partners need 30 days of history before churn is scored.' : 'Not scored yet.'}
            </p>
          )}
        </ScorePanel>
        <ScorePanel
          title="Fraud risk"
          subtitle="From their latest click"
          score={<ScoreBadge score={fraud.data?.score} status={fraud.data?.status} risk />}
          loading={fraud.isLoading}
        >
          {fraud.data ? (
            <div className="space-y-3">
              <WhyBars factors={topFactors(fraud.data.contributing_factors)} risk compact emptyText="Nothing unusual in their recent clicks." />
              <RulePills rules={fraud.data.contributing_factors?.triggered_rules} />
            </div>
          ) : (
            <p className="text-caption text-muted-text">No clicks scored yet.</p>
          )}
        </ScorePanel>
        <ScorePanel
          title="Referral quality"
          subtitle="Average across their sales"
          score={<ScoreBadge score={p?.quality_score} pendingLabel="No sales scored" />}
          loading={partner.isLoading}
        >
          <p className="text-caption text-muted-text">
            Each sale gets its own quality score with an explanation; open a conversion below to compare.
          </p>
        </ScorePanel>
      </div>

      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Panel>
          <PanelHeader title="Recent conversions" description="Latest sales credited to this partner" />
          {conversions.isLoading ? (
            <LoadingRows rows={4} />
          ) : conversions.isError ? (
            <ErrorState error={conversions.error} onRetry={conversions.refetch} />
          ) : !conversions.data.length ? (
            <EmptyState>No sales yet.</EmptyState>
          ) : (
            <TableWrap>
              <Table>
                <THead>
                  <tr>
                    <Th>Order ID</Th>
                    <Th>Date</Th>
                    <Th num>Value</Th>
                    <Th>Attribution</Th>
                    <Th>Quality</Th>
                    <Th num>Commission</Th>
                  </tr>
                </THead>
                <tbody>
                  {conversions.data.map((c) => (
                    <Tr key={c.id}>
                      <Td className="font-medium whitespace-nowrap">{c.external_reference}</Td>
                      <Td className="whitespace-nowrap">{dateTime(c.converted_at)}</Td>
                      <Td num>{money(c.conversion_value)}</Td>
                      <Td className="whitespace-nowrap">{attributionLabel(c)}</Td>
                      <Td>
                        <QualityCell conv={c} />
                      </Td>
                      <Td num>{money(c.commission_amount)}</Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
          )}
        </Panel>

        <div className="space-y-6">
          <Panel>
            <PanelHeader title="Tier" />
            <PanelBody>{dash.data ? <TierProgress tier={dash.data.tier} compact /> : <LoadingRows rows={2} className="p-0" />}</PanelBody>
          </Panel>
          <Panel>
            <PanelHeader
              title="Withdrawals"
              actions={
                <Button asChild variant="ghost" size="sm">
                  <Link to="/admin/payouts">Payouts</Link>
                </Button>
              }
            />
            {withdrawals.isLoading ? (
              <LoadingRows rows={3} />
            ) : !withdrawals.data?.length ? (
              <EmptyState>No withdrawals yet.</EmptyState>
            ) : (
              <TableWrap>
                <Table>
                  <THead>
                    <tr>
                      <Th>Requested</Th>
                      <Th num>Amount</Th>
                      <Th>Status</Th>
                    </tr>
                  </THead>
                  <tbody>
                    {withdrawals.data.slice(0, 6).map((w) => (
                      <Tr key={w.id}>
                        <Td className="whitespace-nowrap">{date(w.requested_at)}</Td>
                        <Td num>{money(w.amount)}</Td>
                        <Td>
                          <StatusPill kind="withdrawal" status={w.status} />
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

      {p && tiers.data && <TierDialog key={p.tier_id} open={tierOpen} onOpenChange={setTierOpen} partner={p} tiers={tiers.data} />}
      {p && (
        <ConfirmDialog
          open={statusOpen}
          onOpenChange={setStatusOpen}
          title={suspended ? `Reactivate ${p.name}?` : `Suspend ${p.name}?`}
          description={
            suspended
              ? 'They can earn commission, create links and withdraw again.'
              : 'Their links stop earning commission, they can’t create links or withdraw, and new sales can’t be recorded for them until you reactivate them.'
          }
          confirmLabel={suspended ? 'Reactivate' : 'Suspend partner'}
          destructive={!suspended}
          onConfirm={toggleStatus}
        />
      )}
    </>
  )
}
