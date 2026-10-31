// -----------------------------------------------------------------------------
// Partner commissions: one row per sale's commission, with its status
// (approved = in your wallet, paid = withdrawn, reversed = taken back after a
// refund or confirmed fraud). Filters and search run on the server.
// -----------------------------------------------------------------------------

import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Download, Info } from 'lucide-react'
import { useState } from 'react'

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
import { downloadCsv, partnerApi } from '@/lib/endpoints'
import { dateTime, humanize, money, percent, signedMoney, toNumber } from '@/lib/format'
import { cn } from '@/lib/utils'

const LIMIT = 25
const FILTERS = [
  { value: '', label: 'All' },
  { value: 'approved', label: 'Earned' },
  { value: 'reversed', label: 'Reversed' },
]

export function commissionRate(c) {
  if (c.commission_type === 'fixed') return 'Fixed'
  const amount = toNumber(c.amount)
  const value = toNumber(c.conversion_value)
  return amount && value ? percent(amount / value) : '—'
}

export function signedCommission(c) {
  const amount = toNumber(c.amount) || 0
  return c.status === 'reversed' ? signedMoney(-amount) : signedMoney(amount)
}

export default function CommissionsPage() {
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const params = { status, search: search.trim(), limit: LIMIT, offset }
  const page = useQuery({
    queryKey: ['my-commissions', params],
    queryFn: () => partnerApi.commissions(params),
    placeholderData: keepPreviousData,
  })
  const totals = page.data?.totals || {}
  const wallet = useQuery({ queryKey: ['wallet'], queryFn: partnerApi.wallet })

  function exportCsv() {
    downloadCsv(
      'referrai-commissions.csv',
      (page.data?.items || []).map((c) => ({
        date: c.converted_at || c.calculated_at,
        order_id: c.external_reference,
        order_value: c.conversion_value,
        commission: c.amount,
        status: c.status,
      })),
    )
  }

  return (
    <>
      <PageHeader
        title="Commissions"
        description="What you've earned on each referred sale."
        actions={
          <Button variant="secondary" onClick={exportCsv} disabled={!page.data?.items.length}>
            <Download />
            Export CSV
          </Button>
        }
      />
      <LedgerStrip
        loading={page.isLoading}
        items={[
          { label: 'Earned', value: money((toNumber(totals.approved) || 0) + (toNumber(totals.paid) || 0)), tone: 'jade', context: 'Added to your wallet' },
          { label: 'Withdrawn', value: money(wallet.data?.total_withdrawn), context: 'Paid out to you' },
          { label: 'Reversed', value: money(totals.reversed || 0), tone: toNumber(totals.reversed) ? 'rose' : 'default', context: 'Refunded or confirmed fraud' },
        ]}
      />
      <Panel>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
          <Segmented
            options={FILTERS}
            value={status}
            onChange={(v) => {
              setStatus(v)
              setOffset(0)
            }}
            label="Filter by status"
            size="sm"
          />
          <SearchInput
            value={search}
            onChange={(v) => {
              setSearch(v)
              setOffset(0)
            }}
            placeholder="Filter by order ID"
          />
        </div>
        {page.isLoading ? (
          <LoadingRows rows={6} />
        ) : page.isError ? (
          <ErrorState error={page.error} onRetry={page.refetch} />
        ) : !page.data.total && !status && !search ? (
          <EmptyState title="No commissions yet">You&apos;ll see a commission here every time a referred customer buys.</EmptyState>
        ) : (
          <>
            <TableWrap className={cn(page.isFetching && 'opacity-70')}>
              <Table>
                <THead>
                  <tr>
                    <Th>Date</Th>
                    <Th>Order ID</Th>
                    <Th num>Order value</Th>
                    <Th num>Rate</Th>
                    <Th num>Commission</Th>
                    <Th>Status</Th>
                  </tr>
                </THead>
                <tbody>
                  {!page.data.items.length && <TableMessage colSpan={6}>No commissions match these filters.</TableMessage>}
                  {page.data.items.map((c) => (
                    <Tr key={c.id}>
                      <Td className="whitespace-nowrap">{dateTime(c.converted_at || c.calculated_at)}</Td>
                      <Td className="font-medium whitespace-nowrap">{c.external_reference}</Td>
                      <Td num>{money(c.conversion_value)}</Td>
                      <Td num title={humanize(c.commission_type)}>
                        {commissionRate(c)}
                      </Td>
                      <Td num className={cn('font-semibold', c.status === 'reversed' ? 'text-rose' : 'text-jade')}>
                        {signedCommission(c)}
                      </Td>
                      <Td>
                        <StatusPill kind="commission" status={c.status} />
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
      <p className="mt-3 flex items-center gap-2 text-label text-muted-text">
        <Info className="size-3.5" aria-hidden />
        Commission is calculated automatically when a sale is recorded, at your tier&apos;s rate at that moment.
      </p>
    </>
  )
}
