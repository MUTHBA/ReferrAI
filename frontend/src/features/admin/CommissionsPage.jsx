// -----------------------------------------------------------------------------
// Admin commissions: every commission across partners, filterable by status,
// searchable by order ID or partner, with "Reverse" for refunds or confirmed
// fraud (takes the amount back from the partner's wallet; audited).
// -----------------------------------------------------------------------------

import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { ConfirmDialog } from '@/components/app/ConfirmDialog'
import { LedgerStrip } from '@/components/app/LedgerStrip'
import { PageHeader } from '@/components/app/PageHeader'
import { Pagination } from '@/components/app/Pagination'
import { SearchInput } from '@/components/app/SearchInput'
import { EmptyState, ErrorState, LoadingRows } from '@/components/app/States'
import { Button } from '@/components/ui/button'
import { Panel } from '@/components/ui/panel'
import { StatusPill } from '@/components/ui/pill'
import { Segmented } from '@/components/ui/segmented'
import { Table, TableMessage, TableWrap, Td, Th, THead, Tr } from '@/components/ui/table'
import { commissionRate, signedCommission } from '@/features/partner/CommissionsPage'
import { adminApi } from '@/lib/endpoints'
import { dateTime, humanize, money, toNumber } from '@/lib/format'
import { cn } from '@/lib/utils'

const LIMIT = 25

export default function CommissionsPage() {
  const qc = useQueryClient()
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const [reversing, setReversing] = useState(null)
  const params = { status, search: search.trim(), limit: LIMIT, offset }
  const page = useQuery({
    queryKey: ['commissions', params],
    queryFn: () => adminApi.commissions(params),
    placeholderData: keepPreviousData,
  })
  const totals = page.data?.totals || {}
  const dash = useQuery({ queryKey: ['admin-dashboard', 30], queryFn: () => adminApi.dashboard(30) })

  async function reverse(reason) {
    await adminApi.reverseCommission(reversing.id, reason)
    toast.success(`Reversed ${money(reversing.amount)} for ${reversing.partner_name}.`)
    qc.invalidateQueries({ queryKey: ['commissions'] })
    qc.invalidateQueries({ queryKey: ['admin-dashboard'] })
  }

  return (
    <>
      <PageHeader title="Commissions" description="What each partner earned on each sale. Reverse a commission after a refund or confirmed fraud." />
      <LedgerStrip
        loading={page.isLoading}
        items={[
          { label: 'Earned by partners', value: money((toNumber(totals.approved) || 0) + (toNumber(totals.paid) || 0)), tone: 'jade', context: 'Credited to wallets' },
          { label: 'Paid out', value: money(dash.data?.kpis.total_paid_out), context: 'Approved and paid withdrawals' },
          { label: 'Reversed', value: money(totals.reversed || 0), tone: toNumber(totals.reversed) ? 'rose' : 'default', context: 'Taken back' },
        ]}
      />
      <Panel>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
          <Segmented
            size="sm"
            label="Filter by status"
            value={status}
            onChange={(v) => {
              setStatus(v)
              setOffset(0)
            }}
            options={[
              { value: '', label: 'All' },
              { value: 'approved', label: 'Earned' },
              { value: 'reversed', label: 'Reversed' },
            ]}
          />
          <SearchInput
            value={search}
            onChange={(v) => {
              setSearch(v)
              setOffset(0)
            }}
            placeholder="Search order ID or partner"
            className="sm:w-72"
          />
        </div>
        {page.isLoading ? (
          <LoadingRows rows={8} />
        ) : page.isError ? (
          <ErrorState error={page.error} onRetry={page.refetch} />
        ) : !page.data.total && !status && !search ? (
          <EmptyState title="No commissions yet">Commissions are created automatically when a sale is recorded.</EmptyState>
        ) : (
          <>
            <TableWrap className={cn(page.isFetching && 'opacity-70')}>
              <Table>
                <THead>
                  <tr>
                    <Th>Date</Th>
                    <Th>Partner</Th>
                    <Th>Order ID</Th>
                    <Th num>Order value</Th>
                    <Th>Type</Th>
                    <Th num>Commission</Th>
                    <Th>Status</Th>
                    <Th>
                      <span className="sr-only">Actions</span>
                    </Th>
                  </tr>
                </THead>
                <tbody>
                  {!page.data.items.length && <TableMessage colSpan={8}>No commissions match these filters.</TableMessage>}
                  {page.data.items.map((c) => (
                    <Tr key={c.id}>
                      <Td className="whitespace-nowrap">{dateTime(c.converted_at || c.calculated_at)}</Td>
                      <Td className="whitespace-nowrap">
                        <Link to={`/admin/partners/${c.partner_id}`} className="font-medium hover:underline">
                          {c.partner_name}
                        </Link>
                      </Td>
                      <Td className="whitespace-nowrap">{c.external_reference}</Td>
                      <Td num>{money(c.conversion_value)}</Td>
                      <Td className="whitespace-nowrap">
                        {humanize(c.commission_type)}
                        <span className="ml-1 text-muted-text">· {commissionRate(c)}</span>
                      </Td>
                      <Td num className={cn('font-semibold', c.status === 'reversed' ? 'text-rose' : 'text-jade')}>
                        {signedCommission(c)}
                      </Td>
                      <Td>
                        <StatusPill kind="commission" status={c.status} />
                      </Td>
                      <Td className="text-right">
                        {c.status !== 'reversed' && (
                          <Button size="sm" variant="ghost" className="text-rose" onClick={() => setReversing(c)}>
                            Reverse
                          </Button>
                        )}
                      </Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
            <Pagination offset={offset} limit={LIMIT} total={page.data.total} onChange={setOffset} noun="commissions" />
          </>
        )}
      </Panel>
      {reversing && (
        <ConfirmDialog
          key={reversing.id}
          open
          onOpenChange={(v) => !v && setReversing(null)}
          title={`Reverse ${money(reversing.amount)} commission for ${reversing.partner_name}?`}
          description="It will be taken back from their wallet. Use this for refunds or confirmed fraud."
          confirmLabel="Reverse commission"
          destructive
          reasonLabel="Reason"
          reasonPlaceholder="e.g. Order returned by customer"
          reasonRequired
          onConfirm={reverse}
        >
          <p className="mb-4 text-caption text-muted-text">If the partner has already withdrawn the money, the reversal is refused.</p>
        </ConfirmDialog>
      )}
    </>
  )
}
