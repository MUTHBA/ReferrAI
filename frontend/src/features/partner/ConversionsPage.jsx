// -----------------------------------------------------------------------------
// Partner conversions: every sale credited to the partner, with how it was
// attributed, its AI referral-quality score and the commission earned. Selecting
// a row opens the details (side panel on desktop, dialog on small screens),
// including the "why" bars behind the quality score.
// -----------------------------------------------------------------------------

import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { PageHeader } from '@/components/app/PageHeader'
import { paginate, Pagination } from '@/components/app/Pagination'
import { ScoreBadge } from '@/components/app/ScoreBadge'
import { SearchInput } from '@/components/app/SearchInput'
import { EmptyState, ErrorState, LoadingRows } from '@/components/app/States'
import { WhyBars } from '@/components/app/WhyBars'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import { Panel } from '@/components/ui/panel'
import { StatusPill } from '@/components/ui/pill'
import { Table, TableMessage, TableWrap, Td, Th, THead, Tr } from '@/components/ui/table'
import { useMediaQuery } from '@/hooks/use-media-query'
import { partnerApi } from '@/lib/endpoints'
import { dateTime, money, percent, signedMoney, toNumber } from '@/lib/format'

import { attributionLabel, deviceLabel, QualityCell, sourceLabel } from './conversion-bits'

const PAGE = 20

function hoursBetween(a, b) {
  if (!a || !b) return null
  return Math.max(0, (new Date(b) - new Date(a)) / 3_600_000)
}

function Row({ label, children }) {
  return (
    <div className="flex items-start justify-between gap-4 py-2 text-caption">
      <dt className="text-muted-text">{label}</dt>
      <dd className="tabular text-right font-medium text-text">{children}</dd>
    </div>
  )
}

export function ConversionDetail({ conv }) {
  const hours = hoursBetween(conv.clicked_at, conv.converted_at)
  const rate =
    conv.commission_type !== 'fixed' && toNumber(conv.commission_amount) && toNumber(conv.conversion_value)
      ? ` (${percent(toNumber(conv.commission_amount) / toNumber(conv.conversion_value))})`
      : ''
  return (
    <div>
      <dl className="divide-y divide-line">
        <Row label="Order value">{money(conv.conversion_value)}</Row>
        <Row label="Date">{dateTime(conv.converted_at)}</Row>
        <Row label="Attribution">{attributionLabel(conv)}</Row>
        {conv.clicked_at && (
          <Row label="Clicked at">
            {dateTime(conv.clicked_at)}
            {hours !== null && (
              <span className="block text-label font-normal text-muted-text">
                {hours < 1 ? 'under an hour' : `${Math.round(hours)} hours`} before the purchase
              </span>
            )}
          </Row>
        )}
        <Row label="Source">{sourceLabel(conv.source)}</Row>
        <Row label="Device">{deviceLabel(conv.device_type)}</Row>
        <Row label="Commission">
          {conv.commission_amount ? (
            <span className="text-jade">
              {signedMoney(conv.commission_amount)}
              {rate}
            </span>
          ) : (
            '—'
          )}
        </Row>
        {conv.commission_status && (
          <Row label="Commission status">
            <StatusPill kind="commission" status={conv.commission_status} />
          </Row>
        )}
      </dl>
      <div className="mt-5 rounded-[8px] border border-line p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <span className="text-body font-semibold text-ink">Referral quality</span>
          <ScoreBadge score={conv.quality_score} status={conv.quality_status} pendingLabel="Scoring…" outOf />
        </div>
        {conv.quality_score !== null && conv.quality_score !== undefined ? (
          <WhyBars
            factors={(conv.quality_factors || []).map((f) => ({ label: f.label || f.feature, effect: Number(f.effect) }))}
          />
        ) : (
          <p className="text-caption text-muted-text">
            {conv.quality_status === 'model_unavailable'
              ? 'The quality model has not been trained yet.'
              : 'The score appears here a few seconds after the sale is recorded.'}
          </p>
        )}
        <p className="mt-3 text-label text-muted-text">
          Quality estimates how likely this sale is to be a genuine, lasting customer. It does not change your commission.
        </p>
      </div>
    </div>
  )
}

export default function ConversionsPage() {
  const list = useQuery({ queryKey: ['conversions', 'all'], queryFn: () => partnerApi.conversions({ limit: 500 }) })
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const [selectedId, setSelectedId] = useState(null)
  const wide = useMediaQuery('(min-width: 1024px)')

  const rows = useMemo(() => {
    const q = search.trim().toLowerCase()
    return (list.data || []).filter((c) => !q || (c.external_reference || '').toLowerCase().includes(q))
  }, [list.data, search])
  const selected = rows.find((c) => c.id === selectedId) || (wide ? rows[0] : null)

  return (
    <>
      <PageHeader
        title="Conversions"
        description="Sales credited to you, how they were attributed, and their AI quality score."
        actions={
          <SearchInput
            value={search}
            onChange={(v) => {
              setSearch(v)
              setOffset(0)
            }}
            placeholder="Search order ID"
          />
        }
      />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Panel>
          {list.isLoading ? (
            <LoadingRows rows={6} />
          ) : list.isError ? (
            <ErrorState error={list.error} onRetry={list.refetch} />
          ) : !list.data.length ? (
            <EmptyState title="No conversions yet">Sales you refer appear here as soon as the shop records them.</EmptyState>
          ) : (
            <>
              <TableWrap>
                <Table>
                  <THead>
                    <tr>
                      <Th>Order ID</Th>
                      <Th>Date</Th>
                      <Th num>Order value</Th>
                      <Th>Attribution</Th>
                      <Th>Quality</Th>
                      <Th num>Commission</Th>
                    </tr>
                  </THead>
                  <tbody>
                    {!rows.length && <TableMessage colSpan={6}>No orders match “{search}”.</TableMessage>}
                    {paginate(rows, offset, PAGE).map((c) => (
                      <Tr
                        key={c.id}
                        onClick={() => setSelectedId(c.id)}
                        selected={wide && selected?.id === c.id}
                        tabIndex={0}
                        onKeyDown={(e) => e.key === 'Enter' && setSelectedId(c.id)}
                        aria-label={`Order ${c.external_reference}`}
                      >
                        <Td className="font-medium whitespace-nowrap">{c.external_reference}</Td>
                        <Td className="whitespace-nowrap">{dateTime(c.converted_at)}</Td>
                        <Td num>{money(c.conversion_value)}</Td>
                        <Td className="whitespace-nowrap">{attributionLabel(c)}</Td>
                        <Td>
                          <QualityCell conv={c} />
                        </Td>
                        <Td num className="font-semibold text-jade">
                          {c.commission_amount ? signedMoney(c.commission_amount) : '—'}
                        </Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              </TableWrap>
              <Pagination offset={offset} limit={PAGE} total={rows.length} onChange={setOffset} noun="conversions" />
            </>
          )}
        </Panel>

        {wide && (
          <Panel className="sticky top-20">
            {selected ? (
              <div className="p-5">
                <h2 className="text-section font-semibold text-ink">Order {selected.external_reference}</h2>
                <p className="mb-3 text-caption text-muted-text">Conversion details</p>
                <ConversionDetail conv={selected} />
              </div>
            ) : (
              <EmptyState>Select a conversion to see its details.</EmptyState>
            )}
          </Panel>
        )}
      </div>

      {!wide && (
        <Dialog open={Boolean(selected)} onOpenChange={(v) => !v && setSelectedId(null)}>
          {selected && (
            <DialogContent title={`Order ${selected.external_reference}`} description="Conversion details">
              <ConversionDetail conv={selected} />
            </DialogContent>
          )}
        </Dialog>
      )}
    </>
  )
}
