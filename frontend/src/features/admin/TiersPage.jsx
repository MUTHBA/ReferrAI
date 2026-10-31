// -----------------------------------------------------------------------------
// Tiers: the commission ladder. A partner moves up automatically when they
// reach BOTH the sales and the revenue target of a higher tier; the new rate
// applies to future sales only. Tiers with partners in them can't be deleted.
// -----------------------------------------------------------------------------

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Info, Pencil, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { ConfirmDialog } from '@/components/app/ConfirmDialog'
import { LedgerStrip } from '@/components/app/LedgerStrip'
import { PageHeader } from '@/components/app/PageHeader'
import { EmptyState, ErrorState, LoadingRows } from '@/components/app/States'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter } from '@/components/ui/dialog'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Panel } from '@/components/ui/panel'
import { Pill } from '@/components/ui/pill'
import { RadioCards } from '@/components/ui/radio-cards'
import { Spinner } from '@/components/ui/spinner'
import { Table, TableWrap, Td, Th, THead, Tr } from '@/components/ui/table'
import { errorMessage } from '@/lib/api'
import { adminApi } from '@/lib/endpoints'
import { money, number, percent, rateLabel, toNumber } from '@/lib/format'

function toForm(tier, nextRank) {
  if (!tier) return { name: '', rank_order: String(nextRank), min_referral_count: '0', min_revenue_contribution: '0', commission_type: 'percentage', rate: '' }
  const type = tier.commission_type === 'fixed' ? 'fixed' : 'percentage'
  const value = toNumber(tier.commission_value)
  return {
    name: tier.name,
    rank_order: String(tier.rank_order),
    min_referral_count: String(tier.min_referral_count),
    min_revenue_contribution: String(toNumber(tier.min_revenue_contribution)),
    commission_type: type,
    rate: type === 'fixed' ? String(value) : String(Math.round(value * 10000) / 100),
  }
}

function TierDialog({ tier, nextRank, partnerCount, onClose }) {
  const qc = useQueryClient()
  const [form, setForm] = useState(() => toForm(tier, nextRank))
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const rate = toNumber(form.rate)
  const rateProblem =
    form.rate === ''
      ? null
      : form.commission_type === 'percentage'
        ? rate === null || rate <= 0 || rate > 100
          ? 'Enter a percentage between 0 and 100.'
          : null
        : rate === null || rate < 0
          ? 'Enter an amount of $0 or more.'
          : null
  const intProblem = (v) => (v === '' || !/^\d+$/.test(v) ? 'Enter a whole number, 0 or more.' : null)
  const revenueProblem = form.min_revenue_contribution === '' || toNumber(form.min_revenue_contribution) === null || toNumber(form.min_revenue_contribution) < 0 ? 'Enter an amount of $0 or more.' : null
  const valid =
    form.name.trim() && !intProblem(form.rank_order) && Number(form.rank_order) > 0 && !intProblem(form.min_referral_count) && !revenueProblem && form.rate !== '' && !rateProblem

  const save = useMutation({
    mutationFn: () => {
      const body = {
        name: form.name.trim(),
        rank_order: Number(form.rank_order),
        min_referral_count: Number(form.min_referral_count),
        min_revenue_contribution: form.min_revenue_contribution,
        commission_type: form.commission_type,
        commission_value: form.commission_type === 'percentage' ? String(Math.round(rate * 100) / 10000) : String(rate),
      }
      return tier ? adminApi.updateTier(tier.id, body) : adminApi.createTier(body)
    },
    onSuccess: (t) => {
      qc.invalidateQueries({ queryKey: ['tiers'] })
      toast.success(tier ? `${t.name} saved.` : `${t.name} created.`)
      onClose()
    },
  })

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent
        wide
        title={tier ? `Edit tier — ${tier.name}` : 'New tier'}
        description={tier ? `Changes apply to future sales for the ${number(partnerCount)} ${partnerCount === 1 ? 'partner' : 'partners'} in this tier.` : 'Partners reach it automatically when they meet both targets.'}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (valid) save.mutate()
          }}
          className="space-y-4"
        >
          <div className="grid gap-4 sm:grid-cols-[2fr_1fr]">
            <Field label="Name">{(p) => <Input {...p} value={form.name} onChange={set('name')} maxLength={100} autoFocus />}</Field>
            <Field label="Rank" helper="1 = lowest" error={form.rank_order && (intProblem(form.rank_order) || Number(form.rank_order) < 1) ? 'Whole number, 1 or more.' : null}>
              {(p) => <Input {...p} inputMode="numeric" value={form.rank_order} onChange={set('rank_order')} />}
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Minimum sales" error={form.min_referral_count !== '' ? intProblem(form.min_referral_count) : null}>
              {(p) => <Input {...p} inputMode="numeric" value={form.min_referral_count} onChange={set('min_referral_count')} />}
            </Field>
            <Field label="Minimum revenue ($)" error={form.min_revenue_contribution !== '' ? revenueProblem : null}>
              {(p) => <Input {...p} inputMode="decimal" value={form.min_revenue_contribution} onChange={set('min_revenue_contribution')} />}
            </Field>
          </div>
          <p className="-mt-2 text-caption text-muted-text">Partners need BOTH targets.</p>
          <div>
            <div className="mb-1.5 text-caption font-medium text-text">Commission type</div>
            <RadioCards
              name="commission_type"
              columns={2}
              value={form.commission_type}
              onChange={(v) => setForm((f) => ({ ...f, commission_type: v, rate: '' }))}
              options={[
                { value: 'percentage', label: 'Percentage of order' },
                { value: 'fixed', label: 'Fixed amount per sale' },
              ]}
            />
          </div>
          <Field label={form.commission_type === 'percentage' ? 'Rate (%)' : 'Amount per sale ($)'} error={rateProblem}>
            {(p) => <Input {...p} inputMode="decimal" value={form.rate} onChange={set('rate')} placeholder={form.commission_type === 'percentage' ? '12' : '10.00'} />}
          </Field>
          {save.isError && <Alert variant="error">{errorMessage(save.error)}</Alert>}
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={!valid || save.isPending}>
              {save.isPending && <Spinner />}
              {tier ? 'Save tier' : 'Create tier'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function TiersPage() {
  const qc = useQueryClient()
  const tiers = useQuery({ queryKey: ['tiers'], queryFn: adminApi.tiers })
  const partners = useQuery({ queryKey: ['partners'], queryFn: () => adminApi.partners() })
  const [editing, setEditing] = useState(null) // tier | 'new'
  const [deleting, setDeleting] = useState(null)
  const sorted = [...(tiers.data || [])].sort((a, b) => a.rank_order - b.rank_order)
  const counts = {}
  for (const p of partners.data || []) if (p.tier_id) counts[p.tier_id] = (counts[p.tier_id] || 0) + 1
  const top = sorted[sorted.length - 1]
  const pctTiers = sorted.filter((t) => t.commission_type !== 'fixed')
  const avg = pctTiers.length ? pctTiers.reduce((a, t) => a + toNumber(t.commission_value), 0) / pctTiers.length : null

  async function remove() {
    await adminApi.deleteTier(deleting.id)
    qc.invalidateQueries({ queryKey: ['tiers'] })
    toast.success(`${deleting.name} deleted.`)
  }

  return (
    <>
      <PageHeader
        title="Tiers"
        description="Commission rates that grow with a partner's sales and revenue."
        actions={
          <Button onClick={() => setEditing('new')}>
            <Plus />
            New tier
          </Button>
        }
      />
      <LedgerStrip
        loading={tiers.isLoading}
        items={[
          { label: 'Tiers', value: number(sorted.length), context: sorted.map((t) => t.name).join(' → ') || 'None yet' },
          { label: 'Partners on the top tier', value: number(top ? counts[top.id] || 0 : 0), context: top ? top.name : '—' },
          { label: 'Average percentage rate', value: avg === null ? '—' : percent(avg), context: 'Across percentage tiers' },
        ]}
      />
      <Panel>
        {tiers.isLoading ? (
          <LoadingRows rows={3} />
        ) : tiers.isError ? (
          <ErrorState error={tiers.error} onRetry={tiers.refetch} />
        ) : !sorted.length ? (
          <EmptyState title="No tiers yet" action={<Button onClick={() => setEditing('new')}>New tier</Button>}>
            Create a starting tier so new partners get a commission rate.
          </EmptyState>
        ) : (
          <TableWrap>
            <Table>
              <THead>
                <tr>
                  <Th>Rank</Th>
                  <Th>Tier</Th>
                  <Th>Needs</Th>
                  <Th>Commission</Th>
                  <Th num>Partners</Th>
                  <Th>
                    <span className="sr-only">Actions</span>
                  </Th>
                </tr>
              </THead>
              <tbody>
                {sorted.map((t) => {
                  const n = counts[t.id] || 0
                  return (
                    <Tr key={t.id}>
                      <Td className="tabular w-16 text-muted-text">{t.rank_order}</Td>
                      <Td className="font-semibold text-ink">{t.name}</Td>
                      <Td className="whitespace-nowrap">
                        {Number(t.min_referral_count) === 0 && toNumber(t.min_revenue_contribution) === 0
                          ? 'Starting tier'
                          : `${number(t.min_referral_count)} sales and ${money(t.min_revenue_contribution, { round: true })} revenue`}
                      </Td>
                      <Td className="whitespace-nowrap">
                        <Pill tone="jade">{rateLabel(t.commission_type, t.commission_value)}</Pill>
                      </Td>
                      <Td num>{number(n)}</Td>
                      <Td className="text-right whitespace-nowrap">
                        <Button size="sm" variant="ghost" onClick={() => setEditing(t)}>
                          <Pencil />
                          Edit
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-rose"
                          disabled={n > 0}
                          title={n > 0 ? `Move its ${n} partners to another tier first` : undefined}
                          onClick={() => setDeleting(t)}
                        >
                          <Trash2 />
                          Delete
                        </Button>
                      </Td>
                    </Tr>
                  )
                })}
              </tbody>
            </Table>
          </TableWrap>
        )}
      </Panel>
      <p className="mt-3 flex items-center gap-2 text-label text-muted-text">
        <Info className="size-3.5 shrink-0" aria-hidden />
        Partners move up automatically when they reach a tier. Upgrades apply to future sales only.
      </p>

      {editing && (
        <TierDialog
          tier={editing === 'new' ? null : editing}
          nextRank={(sorted[sorted.length - 1]?.rank_order || 0) + 1}
          partnerCount={editing === 'new' ? 0 : counts[editing.id] || 0}
          onClose={() => setEditing(null)}
        />
      )}
      {deleting && (
        <ConfirmDialog
          open
          onOpenChange={(v) => !v && setDeleting(null)}
          title={`Delete ${deleting.name}?`}
          description="No partners are in this tier. Past commissions keep the rate they were paid at."
          confirmLabel="Delete tier"
          destructive
          onConfirm={remove}
        />
      )}
    </>
  )
}
