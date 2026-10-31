// -----------------------------------------------------------------------------
// Payouts: partner withdrawal requests. Pending -> Approve or Reject (the money
// goes back to the partner's wallet). Approved -> Mark as paid once the money
// has been sent outside ReferrAI. Requests under the auto-approve threshold
// skip review unless the partner has an open fraud alert.
// -----------------------------------------------------------------------------

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Info } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { ConfirmDialog } from '@/components/app/ConfirmDialog'
import { LedgerStrip } from '@/components/app/LedgerStrip'
import { PageHeader } from '@/components/app/PageHeader'
import { paginate, Pagination } from '@/components/app/Pagination'
import { SearchInput } from '@/components/app/SearchInput'
import { EmptyState, ErrorState, LoadingRows } from '@/components/app/States'
import { Button } from '@/components/ui/button'
import { Panel } from '@/components/ui/panel'
import { Pill, StatusPill } from '@/components/ui/pill'
import { Segmented } from '@/components/ui/segmented'
import { Table, TableMessage, TableWrap, Td, Th, THead, Tr } from '@/components/ui/table'
import { adminApi } from '@/lib/endpoints'
import { dateTime, money, number, toNumber } from '@/lib/format'

const PAGE = 20
const TABS = [
  { value: 'pending', label: 'Pending review' },
  { value: 'approved', label: 'Approved, awaiting payment' },
  { value: 'paid', label: 'Paid' },
  { value: 'rejected', label: 'Rejected' },
]

const sumOf = (list) => list.reduce((a, w) => a + (toNumber(w.amount) || 0), 0)

export default function PayoutsPage() {
  const qc = useQueryClient()
  const list = useQuery({ queryKey: ['withdrawals', {}], queryFn: () => adminApi.withdrawals() })
  const settings = useQuery({ queryKey: ['settings'], queryFn: adminApi.settings })
  const [tab, setTab] = useState('pending')
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const [action, setAction] = useState(null) // { kind: 'approve'|'reject'|'paid', w }

  const all = useMemo(() => list.data || [], [list.data])
  const byStatus = (s) => all.filter((w) => w.status === s)
  const rows = useMemo(() => {
    const q = search.trim().toLowerCase()
    return all
      .filter((w) => w.status === tab)
      .filter((w) => !q || [w.partner_name, w.partner_email].some((v) => (v || '').toLowerCase().includes(q)))
  }, [all, tab, search])
  const threshold = settings.data?.find((s) => s.key === 'wallet.auto_approval_threshold')?.value

  function refresh() {
    qc.invalidateQueries({ queryKey: ['withdrawals'] })
    qc.invalidateQueries({ queryKey: ['admin-dashboard'] })
  }

  async function run(reason) {
    const { kind, w } = action
    if (kind === 'approve') {
      await adminApi.reviewWithdrawal(w.id, 'approved', reason)
      toast.success(`Approved ${money(w.amount)} for ${w.partner_name}. Send the money, then mark it as paid.`)
    } else if (kind === 'reject') {
      await adminApi.reviewWithdrawal(w.id, 'rejected', reason)
      toast.success(`Rejected. ${money(w.amount)} is back in ${w.partner_name}'s wallet.`)
    } else {
      await adminApi.markPaid(w.id, reason)
      toast.success(`Marked ${money(w.amount)} to ${w.partner_name} as paid.`)
    }
    refresh()
  }

  const dialog = action && {
    approve: {
      title: `Approve ${money(action.w.amount)} for ${action.w.partner_name}?`,
      description: 'The request moves to "Approved, awaiting payment". Send the money outside ReferrAI, then mark it as paid.',
      confirmLabel: 'Approve payout',
      reasonLabel: 'Note (optional)',
      warning: action.w.open_fraud_flag ? 'This partner has an open fraud alert. Review it before approving.' : null,
    },
    reject: {
      title: `Reject ${money(action.w.amount)} for ${action.w.partner_name}?`,
      description: 'The amount goes back to the partner’s wallet. They will see your reason.',
      confirmLabel: 'Reject request',
      destructive: true,
      reasonLabel: 'Reason',
      reasonPlaceholder: 'e.g. Open fraud investigation',
      reasonRequired: true,
    },
    paid: {
      title: 'Mark as paid?',
      description: `Confirm you've sent ${money(action.w.amount)} to ${action.w.partner_name} outside ReferrAI.`,
      confirmLabel: 'Mark as paid',
      reasonLabel: 'Payment reference (optional)',
    },
  }[action.kind]

  return (
    <>
      <PageHeader title="Payouts" description="Withdrawal requests from partners, from review to payment." />
      <LedgerStrip
        loading={list.isLoading}
        items={[
          { label: 'Pending review', value: money(sumOf(byStatus('pending'))), tone: byStatus('pending').length ? 'amber' : 'default', context: `${number(byStatus('pending').length)} requests` },
          { label: 'Approved, awaiting payment', value: money(sumOf(byStatus('approved'))), context: `${number(byStatus('approved').length)} to send` },
          { label: 'Paid', value: money(sumOf(byStatus('paid'))), tone: 'jade', context: `${number(byStatus('paid').length)} payouts` },
          { label: 'Rejected', value: money(sumOf(byStatus('rejected'))), context: 'Returned to wallets' },
        ]}
      />
      <Panel>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
          <Segmented
            size="sm"
            label="Payout status"
            value={tab}
            onChange={(v) => {
              setTab(v)
              setOffset(0)
            }}
            options={TABS.map((t) => ({ ...t, count: byStatus(t.value).length }))}
          />
          <SearchInput
            value={search}
            onChange={(v) => {
              setSearch(v)
              setOffset(0)
            }}
            placeholder="Search partner"
          />
        </div>
        {threshold !== undefined && (
          <p className="flex items-center gap-2 border-b border-line px-4 py-2.5 text-caption text-muted-text">
            <Info className="size-4 shrink-0" aria-hidden />
            Requests under {money(threshold)} are approved automatically unless the partner has an open fraud alert.
          </p>
        )}
        {list.isLoading ? (
          <LoadingRows rows={5} />
        ) : list.isError ? (
          <ErrorState error={list.error} onRetry={list.refetch} />
        ) : !all.length ? (
          <EmptyState title="No withdrawal requests yet">Requests appear here when partners withdraw from their wallet.</EmptyState>
        ) : (
          <>
            <TableWrap>
              <Table>
                <THead>
                  <tr>
                    <Th>Requested</Th>
                    <Th>Partner</Th>
                    <Th num>Amount</Th>
                    <Th num>Wallet balance</Th>
                    <Th>Fraud alert</Th>
                    <Th>Status</Th>
                    <Th>{tab === 'pending' || tab === 'approved' ? <span className="sr-only">Actions</span> : 'Note'}</Th>
                  </tr>
                </THead>
                <tbody>
                  {!rows.length && <TableMessage colSpan={7}>Nothing here.</TableMessage>}
                  {paginate(rows, offset, PAGE).map((w) => (
                    <Tr key={w.id}>
                      <Td className="whitespace-nowrap">{dateTime(w.requested_at)}</Td>
                      <Td className="max-w-[220px]">
                        <Link to={`/admin/partners/${w.partner_id}`} className="block truncate font-semibold text-ink hover:underline">
                          {w.partner_name}
                        </Link>
                        <span className="block truncate text-label text-muted-text">{w.partner_email}</span>
                      </Td>
                      <Td num className="font-semibold">
                        {money(w.amount)}
                      </Td>
                      <Td num>{money(w.wallet_balance)}</Td>
                      <Td>{w.open_fraud_flag ? <Pill tone="rose">Open alert</Pill> : <span className="text-muted-text">None</span>}</Td>
                      <Td>
                        <StatusPill kind="withdrawal" status={w.status} />
                        {w.status !== 'pending' && !w.requires_manual_review && (
                          <span className="mt-0.5 block text-label text-muted-text">Auto-approved</span>
                        )}
                      </Td>
                      <Td className="whitespace-nowrap text-right">
                        {w.status === 'pending' && (
                          <>
                            <Button size="sm" onClick={() => setAction({ kind: 'approve', w })}>
                              Approve
                            </Button>
                            <Button size="sm" variant="ghost" className="ml-1 text-rose" onClick={() => setAction({ kind: 'reject', w })}>
                              Reject
                            </Button>
                          </>
                        )}
                        {w.status === 'approved' && (
                          <Button size="sm" variant="secondary" onClick={() => setAction({ kind: 'paid', w })}>
                            Mark as paid
                          </Button>
                        )}
                        {(w.status === 'paid' || w.status === 'rejected') && (
                          <span className="block max-w-[220px] truncate text-left text-caption text-muted-text" title={w.notes || ''}>
                            {w.notes || '—'}
                          </span>
                        )}
                      </Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
            <Pagination offset={offset} limit={PAGE} total={rows.length} onChange={setOffset} noun="requests" />
          </>
        )}
      </Panel>
      {action && (
        <ConfirmDialog
          key={`${action.kind}-${action.w.id}`}
          open
          onOpenChange={(v) => !v && setAction(null)}
          onConfirm={run}
          {...dialog}
        />
      )}
    </>
  )
}
