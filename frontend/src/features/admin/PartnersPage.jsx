// -----------------------------------------------------------------------------
// Admin partners list: search, status and tier filters, sort, AI score
// columns (rank, churn risk, fraud risk) and a CSV export. Rows open the
// partner detail page.
// -----------------------------------------------------------------------------

import { useQuery } from '@tanstack/react-query'
import { Download } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { LedgerStrip } from '@/components/app/LedgerStrip'
import { PageHeader } from '@/components/app/PageHeader'
import { paginate, Pagination } from '@/components/app/Pagination'
import { ScoreBadge } from '@/components/app/ScoreBadge'
import { SearchInput } from '@/components/app/SearchInput'
import { EmptyState, ErrorState, LoadingRows } from '@/components/app/States'
import { Button } from '@/components/ui/button'
import { Panel } from '@/components/ui/panel'
import { StatusPill } from '@/components/ui/pill'
import { Segmented } from '@/components/ui/segmented'
import { Select } from '@/components/ui/select'
import { Table, TableMessage, TableWrap, Td, Th, THead, Tr } from '@/components/ui/table'
import { errorMessage } from '@/lib/api'
import { adminApi, downloadReport } from '@/lib/endpoints'
import { date, money, number, toNumber } from '@/lib/format'

const PAGE = 20
const SORTS = {
  newest: { label: 'Newest first', fn: (a, b) => new Date(b.created_at) - new Date(a.created_at) },
  rank: { label: 'Rank score', fn: (a, b) => (b.rank_score ?? -1) - (a.rank_score ?? -1) },
  revenue: { label: 'Revenue', fn: (a, b) => toNumber(b.total_revenue_contribution) - toNumber(a.total_revenue_contribution) },
  churn: { label: 'Churn risk', fn: (a, b) => (b.churn_score ?? -1) - (a.churn_score ?? -1) },
  fraud: { label: 'Fraud risk', fn: (a, b) => (b.fraud_score ?? -1) - (a.fraud_score ?? -1) },
  name: { label: 'Name', fn: (a, b) => a.name.localeCompare(b.name) },
}

export default function PartnersPage() {
  const navigate = useNavigate()
  const partners = useQuery({ queryKey: ['partners'], queryFn: () => adminApi.partners() })
  const tiers = useQuery({ queryKey: ['tiers'], queryFn: adminApi.tiers })
  const [status, setStatus] = useState('')
  const [tier, setTier] = useState('')
  const [sort, setSort] = useState('newest')
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const all = useMemo(() => partners.data || [], [partners.data])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return all
      .filter((p) => !status || p.status === status)
      .filter((p) => !tier || p.tier_id === tier)
      .filter((p) => !q || [p.name, p.email, p.business_name].some((v) => (v || '').toLowerCase().includes(q)))
      .sort(SORTS[sort].fn)
  }, [all, status, tier, search, sort])

  const count = (s) => all.filter((p) => p.status === s).length
  const revenue = all.reduce((a, p) => a + (toNumber(p.total_revenue_contribution) || 0), 0)
  const reset = () => setOffset(0)

  async function exportCsv() {
    try {
      await downloadReport('partners')
    } catch (e) {
      toast.error(errorMessage(e, 'The export failed.'))
    }
  }

  return (
    <>
      <PageHeader
        title="Partners"
        description="Everyone referring sales, with their tier and AI scores."
        actions={
          <Button variant="secondary" onClick={exportCsv}>
            <Download />
            Export CSV
          </Button>
        }
      />
      <LedgerStrip
        loading={partners.isLoading}
        items={[
          { label: 'Partners', value: number(all.length), context: `${number(all.filter((p) => Date.now() - new Date(p.created_at) < 7 * 864e5).length)} joined this week` },
          { label: 'Active', value: number(count('active')), tone: 'jade', context: 'Can earn and withdraw' },
          { label: 'Suspended', value: number(count('suspended')), tone: count('suspended') ? 'rose' : 'default', context: `${number(count('pending'))} pending` },
          { label: 'Revenue referred', value: money(revenue, { round: true }), context: 'All time' },
        ]}
      />
      <Panel>
        <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
          <Segmented
            size="sm"
            label="Filter by status"
            value={status}
            onChange={(v) => {
              setStatus(v)
              reset()
            }}
            options={[
              { value: '', label: 'All', count: all.length },
              { value: 'active', label: 'Active', count: count('active') },
              { value: 'suspended', label: 'Suspended', count: count('suspended') },
              { value: 'pending', label: 'Pending', count: count('pending') },
            ]}
          />
          <Select
            aria-label="Filter by tier"
            value={tier}
            onChange={(e) => {
              setTier(e.target.value)
              reset()
            }}
            className="w-36"
          >
            <option value="">All tiers</option>
            {(tiers.data || []).map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </Select>
          <Select aria-label="Sort" value={sort} onChange={(e) => setSort(e.target.value)} className="w-48">
            {Object.entries(SORTS).map(([key, s]) => (
              <option key={key} value={key}>
                Sort: {s.label}
              </option>
            ))}
          </Select>
          <SearchInput
            value={search}
            onChange={(v) => {
              setSearch(v)
              reset()
            }}
            placeholder="Search name, email or business"
            className="sm:ml-auto sm:w-72"
          />
        </div>
        {partners.isLoading ? (
          <LoadingRows rows={8} />
        ) : partners.isError ? (
          <ErrorState error={partners.error} onRetry={partners.refetch} />
        ) : !all.length ? (
          <EmptyState title="No partners yet">Partners appear here when they sign up.</EmptyState>
        ) : (
          <>
            <TableWrap>
              <Table>
                <THead>
                  <tr>
                    <Th>Partner</Th>
                    <Th>Tier</Th>
                    <Th num>Sales</Th>
                    <Th num>Revenue</Th>
                    <Th>Rank</Th>
                    <Th>Churn risk</Th>
                    <Th>Fraud risk</Th>
                    <Th>Status</Th>
                    <Th>Joined</Th>
                  </tr>
                </THead>
                <tbody>
                  {!filtered.length && <TableMessage colSpan={9}>No partners match these filters.</TableMessage>}
                  {paginate(filtered, offset, PAGE).map((p) => (
                    <Tr
                      key={p.id}
                      onClick={() => navigate(`/admin/partners/${p.id}`)}
                      tabIndex={0}
                      onKeyDown={(e) => e.key === 'Enter' && navigate(`/admin/partners/${p.id}`)}
                    >
                      <Td className="max-w-[260px]">
                        <div className="truncate font-semibold text-ink">{p.name}</div>
                        <div className="truncate text-label text-muted-text">{p.email}</div>
                      </Td>
                      <Td className="whitespace-nowrap">{p.tier_name || '—'}</Td>
                      <Td num>{number(p.total_referral_count)}</Td>
                      <Td num>{money(p.total_revenue_contribution)}</Td>
                      <Td>
                        <ScoreBadge score={p.rank_score} pendingLabel="—" />
                      </Td>
                      <Td>
                        <ScoreBadge score={p.churn_score} risk pendingLabel="—" />
                      </Td>
                      <Td>
                        <ScoreBadge score={p.fraud_score} risk pendingLabel="—" />
                      </Td>
                      <Td>
                        <StatusPill kind="partner" status={p.status} />
                      </Td>
                      <Td className="whitespace-nowrap text-muted-text">{date(p.created_at)}</Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
            <Pagination offset={offset} limit={PAGE} total={filtered.length} onChange={setOffset} noun="partners" />
          </>
        )}
      </Panel>
    </>
  )
}
