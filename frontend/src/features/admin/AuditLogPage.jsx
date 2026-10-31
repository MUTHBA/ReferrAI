// -----------------------------------------------------------------------------
// Audit log: every admin action and every automatic money or tier event, newest
// first. Rows are read-only. Expand a row to see the values before and after.
// -----------------------------------------------------------------------------

import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Bot, ChevronDown, User } from 'lucide-react'
import { Fragment, useMemo, useState } from 'react'

import { LedgerStrip } from '@/components/app/LedgerStrip'
import { PageHeader } from '@/components/app/PageHeader'
import { Pagination } from '@/components/app/Pagination'
import { SearchInput } from '@/components/app/SearchInput'
import { EmptyState, ErrorState, LoadingRows } from '@/components/app/States'
import { Pill } from '@/components/ui/pill'
import { Panel } from '@/components/ui/panel'
import { Select } from '@/components/ui/select'
import { Table, TableMessage, TableWrap, Td, Th, THead, Tr } from '@/components/ui/table'
import { adminApi } from '@/lib/endpoints'
import { dateTime, humanize, money, number } from '@/lib/format'
import { cn } from '@/lib/utils'

const LIMIT = 30

const ACTION_LABELS = {
  'settings.updated': ['Setting changed', 'cobalt'],
  'withdrawal.auto_approved': ['Payout auto-approved', 'jade'],
  'withdrawal.approved': ['Payout approved', 'jade'],
  'withdrawal.rejected': ['Payout rejected', 'rose'],
  'withdrawal.paid': ['Payout paid', 'jade'],
  'commission.reversed': ['Commission reversed', 'rose'],
  'fraud_flag.confirmed': ['Fraud confirmed', 'rose'],
  'fraud_flag.dismissed': ['Fraud alert dismissed', 'grey'],
  'partner.status_changed': ['Partner status changed', 'amber'],
  'partner.updated': ['Partner updated', 'grey'],
  'partner.tier_upgraded': ['Tier upgrade', 'jade'],
  'tier.created': ['Tier created', 'cobalt'],
  'tier.updated': ['Tier updated', 'cobalt'],
  'tier.deleted': ['Tier deleted', 'rose'],
  'discovery.status_changed': ['Candidate updated', 'grey'],
  'discovery.candidates_scored': ['Candidates scored', 'cobalt'],
  'ai.training_started': ['Model training started', 'cobalt'],
  'ai.churn_scoring_run': ['Churn scoring run', 'cobalt'],
  'ai.ranking_run': ['Ranking run', 'cobalt'],
  'ai.synthetic_data_generated': ['Synthetic data generated', 'cobalt'],
}

const SETTING_NAMES = {
  'commission.default_type': 'Default commission type',
  'commission.default_percentage': 'Default commission rate',
  'commission.default_fixed_amount': 'Default fixed commission',
  'wallet.min_withdrawal_amount': 'Minimum withdrawal',
  'wallet.auto_approval_threshold': 'Auto-approve threshold',
  'referral.attribution_model': 'Attribution model',
  'referral.attribution_window_days': 'Attribution window',
  'fraud.alert_threshold': 'Fraud alert threshold',
  'fraud.max_clicks_per_hour': 'Max clicks per IP per hour',
  'fraud.max_device_partner_spread': 'Max partners per device',
  'fraud.rule_weight': 'Fraud rule weight',
  'churn.alert_threshold': 'Churn alert threshold',
  'ranking.weights': 'Ranking weights',
  'ai.batch_scoring_interval_hours': 'Scoring interval',
}

function settingValue(key, value) {
  if (value === null || value === undefined) return '—'
  if (key === 'commission.default_percentage') return `${Math.round(Number(value) * 10000) / 100}%`
  if (/amount|threshold$/.test(key) && key.startsWith('wallet')) return money(value)
  if (key === 'commission.default_fixed_amount') return money(value)
  if (key === 'referral.attribution_window_days') return `${value} days`
  if (key === 'ai.batch_scoring_interval_hours') return `${value} hours`
  if (typeof value === 'object') return Object.entries(value).map(([k, v]) => `${k} ${v}`).join(', ')
  return humanize(String(value))
}

/** One plain sentence for the row. */
function describe(e) {
  const nv = e.new_value || {}
  const ov = e.old_value || {}
  const who = e.partner_name
  switch (e.action) {
    case 'settings.updated':
      return `Changed ${(SETTING_NAMES[nv.key] || nv.key || 'a setting').toLowerCase()} from ${settingValue(nv.key, ov.value)} to ${settingValue(nv.key, nv.value)}`
    case 'withdrawal.auto_approved':
      return `Auto-approved ${money(nv.amount)} payout${who ? ` for ${who}` : ''} (under ${money(nv.threshold)})`
    case 'withdrawal.approved':
      return `Approved ${money(nv.amount)} payout${who ? ` for ${who}` : ''}`
    case 'withdrawal.rejected':
      return `Rejected ${money(nv.amount)} payout${who ? ` for ${who}` : ''}`
    case 'withdrawal.paid':
      return `Marked ${money(nv.amount)} payout${who ? ` to ${who}` : ''} as paid`
    case 'commission.reversed':
      return `Reversed ${money(nv.amount)} commission${who ? ` for ${who}` : ''}`
    case 'fraud_flag.confirmed':
      return `Confirmed fraud alert${who ? ` for ${who}` : ''}`
    case 'fraud_flag.dismissed':
      return `Dismissed fraud alert${who ? ` for ${who}` : ''}`
    case 'partner.status_changed':
      return `Changed ${who || 'partner'} from ${humanize(ov.status).toLowerCase()} to ${humanize(nv.status).toLowerCase()}`
    case 'partner.updated':
      return `Updated ${who || 'a partner'} (${Object.keys(nv).map((k) => humanize(k).toLowerCase()).join(', ')})`
    case 'partner.tier_upgraded':
      return `Upgraded ${who || 'a partner'} to ${nv.tier_name} (automatic)`
    case 'tier.created':
      return `Created tier ${nv.name || ''}`.trim()
    case 'tier.updated':
      return `Updated tier ${ov.name || nv.name || ''}`.trim()
    case 'tier.deleted':
      return `Deleted tier ${ov.name || ''}`.trim()
    case 'discovery.status_changed':
      return `Marked candidate ${nv.candidate_name || ''} as ${nv.status}`
    case 'discovery.candidates_scored':
      return `Scored ${number(nv.count)} discovery ${nv.count === 1 ? 'candidate' : 'candidates'}`
    case 'ai.training_started':
      return `Started training (${(nv.models || []).join(', ')})`
    case 'ai.churn_scoring_run':
      return `Ran churn scoring for ${number(nv.partners_scored)} partners`
    case 'ai.ranking_run':
      return `Ran ranking for ${number(nv.partners_scored)} partners`
    default:
      return humanize(e.action)
  }
}

function prettyKey(k) {
  return { tier_id: 'Tier', rank_order: 'Rank', min_referral_count: 'Minimum sales', min_revenue_contribution: 'Minimum revenue', commission_value: 'Commission value', commission_type: 'Commission type' }[k] || humanize(k)
}

function prettyValue(k, v) {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'object') return JSON.stringify(v)
  if (/amount|threshold|revenue|recent_auto_total/.test(k)) return money(v)
  if (k.endsWith('_id') || k === 'partner_id') return String(v).slice(0, 8) + '…'
  return humanize(String(v))
}

function ValueTable({ title, value, tone }) {
  let rows = []
  if (value && typeof value === 'object' && 'key' in value && 'value' in value) {
    rows = [[SETTING_NAMES[value.key] || value.key, settingValue(value.key, value.value)]]
  } else if (value && typeof value === 'object') {
    rows = Object.entries(value).map(([k, v]) => [prettyKey(k), prettyValue(k, v)])
  }
  return (
    <div className={cn('min-w-0 rounded-[8px] border p-3', tone === 'old' ? 'border-rose/30 bg-rose-soft/40' : 'border-jade/30 bg-jade-soft/40')}>
      <div className="mb-2 text-label font-semibold text-muted-text">{title}</div>
      {rows.length ? (
        <dl className="space-y-1 text-caption">
          {rows.map(([k, v]) => (
            <div key={k} className="flex justify-between gap-4">
              <dt className="text-muted-text">{k}</dt>
              <dd className="tabular text-right font-medium break-all">{v}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="text-caption text-muted-text">—</p>
      )}
    </div>
  )
}

const RANGES = {
  '1': { label: 'Last 24 hours', hours: 24 },
  '7': { label: 'Last 7 days', hours: 24 * 7 },
  '30': { label: 'Last 30 days', hours: 24 * 30 },
  all: { label: 'All time', hours: null },
}

export default function AuditLogPage() {
  const [search, setSearch] = useState('')
  const [action, setAction] = useState('')
  const [actor, setActor] = useState('')
  const [range, setRange] = useState('7')
  const [offset, setOffset] = useState(0)
  const [open, setOpen] = useState(null)
  const since = useMemo(() => {
    const h = RANGES[range].hours
    return h ? new Date(Date.now() - h * 3_600_000).toISOString() : null
  }, [range])
  const params = { search: search.trim(), action, actor, since, limit: LIMIT, offset }
  const page = useQuery({ queryKey: ['audit-logs', params], queryFn: () => adminApi.auditLogs(params), placeholderData: keepPreviousData })
  const actions = useQuery({ queryKey: ['audit-actions'], queryFn: adminApi.auditActions })
  const stats = page.data?.stats
  const reset = () => setOffset(0)

  return (
    <>
      <PageHeader title="Audit log" description="Every admin action and every automatic money or tier event. Entries can't be edited." />
      <LedgerStrip
        loading={page.isLoading}
        items={[
          { label: 'Events, last 24 hours', value: number(stats?.events_24h), context: 'All sources' },
          { label: 'By admins', value: number(stats?.admin_24h), context: 'Last 24 hours' },
          { label: 'By the system', value: number(stats?.system_24h), context: 'Auto-approvals, tier upgrades' },
        ]}
      />
      <Panel>
        <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
          <SearchInput
            value={search}
            onChange={(v) => {
              setSearch(v)
              reset()
            }}
            placeholder="Search partner, admin, IP or value"
            className="sm:w-72"
          />
          <Select aria-label="Action" value={action} onChange={(e) => (setAction(e.target.value), reset())} className="w-52">
            <option value="">All actions</option>
            {(actions.data || []).map((a) => (
              <option key={a} value={a}>
                {ACTION_LABELS[a]?.[0] || humanize(a)}
              </option>
            ))}
          </Select>
          <Select aria-label="Who" value={actor} onChange={(e) => (setActor(e.target.value), reset())} className="w-36">
            <option value="">Everyone</option>
            <option value="admin">Admins</option>
            <option value="system">System</option>
          </Select>
          <Select aria-label="Date range" value={range} onChange={(e) => (setRange(e.target.value), reset())} className="w-40">
            {Object.entries(RANGES).map(([k, r]) => (
              <option key={k} value={k}>
                {r.label}
              </option>
            ))}
          </Select>
        </div>
        {page.isLoading ? (
          <LoadingRows rows={8} />
        ) : page.isError ? (
          <ErrorState error={page.error} onRetry={page.refetch} />
        ) : !page.data.total && !search && !action && !actor && range === 'all' ? (
          <EmptyState title="Nothing recorded yet">Admin actions and automatic payouts and upgrades appear here.</EmptyState>
        ) : (
          <>
            <TableWrap className={cn(page.isFetching && 'opacity-70')}>
              <Table>
                <THead>
                  <tr>
                    <Th>When</Th>
                    <Th>Who</Th>
                    <Th>Action</Th>
                    <Th>IP address</Th>
                    <Th>
                      <span className="sr-only">Details</span>
                    </Th>
                  </tr>
                </THead>
                <tbody>
                  {!page.data.items.length && <TableMessage colSpan={5}>No entries match these filters.</TableMessage>}
                  {page.data.items.map((e) => {
                    const [label, tone] = ACTION_LABELS[e.action] || [humanize(e.action), 'grey']
                    const expanded = open === e.id
                    return (
                      <Fragment key={e.id}>
                        <Tr onClick={() => setOpen(expanded ? null : e.id)} aria-expanded={expanded}>
                          <Td className="whitespace-nowrap">{dateTime(e.created_at)}</Td>
                          <Td className="whitespace-nowrap">
                            <span className="inline-flex items-center gap-1.5">
                              {e.actor_email ? <User className="size-3.5 text-muted-text" aria-hidden /> : <Bot className="size-3.5 text-muted-text" aria-hidden />}
                              {e.actor_email || 'System'}
                            </span>
                          </Td>
                          <Td className="min-w-72">
                            <Pill tone={tone} className="mb-1">
                              {label}
                            </Pill>
                            <div className="text-caption text-text">{describe(e)}</div>
                          </Td>
                          <Td className="tabular whitespace-nowrap text-muted-text">{e.ip_address || '—'}</Td>
                          <Td className="w-10 text-right">
                            <ChevronDown className={cn('inline size-4 text-muted-text transition-transform', expanded && 'rotate-180')} aria-hidden />
                          </Td>
                        </Tr>
                        {expanded && (
                          <tr className="border-b border-line bg-canvas/50">
                            <td colSpan={5} className="px-4 py-4">
                              <div className="grid gap-3 md:grid-cols-2">
                                <ValueTable title="Before" value={e.old_value} tone="old" />
                                <ValueTable title="After" value={e.new_value} tone="new" />
                              </div>
                              {(e.new_value?.notes || e.new_value?.reason) && (
                                <p className="mt-3 text-caption">
                                  <span className="text-muted-text">Note: </span>
                                  {e.new_value.notes || e.new_value.reason}
                                </p>
                              )}
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    )
                  })}
                </tbody>
              </Table>
            </TableWrap>
            <Pagination offset={offset} limit={LIMIT} total={page.data.total} onChange={setOffset} noun="entries" />
          </>
        )}
      </Panel>
    </>
  )
}
