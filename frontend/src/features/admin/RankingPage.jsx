// -----------------------------------------------------------------------------
// Partner ranking: a weighted mix of referral quality, churn resistance
// (100 − churn risk), sales volume and revenue, each 0–100 (volume and revenue
// relative to the best active partner). A component with no score yet counts
// as a neutral 50. Weights are set in Settings.
// -----------------------------------------------------------------------------

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, RefreshCw } from 'lucide-react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { RANK_COMPONENTS } from '@/components/app/ai-labels'
import { PageHeader } from '@/components/app/PageHeader'
import { ScoreBadge } from '@/components/app/ScoreBadge'
import { EmptyState, ErrorState, LoadingRows } from '@/components/app/States'
import { Button } from '@/components/ui/button'
import { Panel } from '@/components/ui/panel'
import { Pill } from '@/components/ui/pill'
import { Spinner } from '@/components/ui/spinner'
import { Table, TableWrap, Td, Th, THead, Tr } from '@/components/ui/table'
import { errorMessage } from '@/lib/api'
import { adminApi, downloadCsv } from '@/lib/endpoints'
import { date, number } from '@/lib/format'
import { cn } from '@/lib/utils'

function ComponentCell({ factors, name }) {
  const components = factors?.components
  if (!components) return <Td className="text-muted-text">—</Td>
  const neutral = (factors.neutral_defaults || []).includes(name)
  const value = Math.round(Number(components[name]) || 0)
  return (
    <Td className="w-32">
      {neutral ? (
        <span className="text-label text-muted-text italic" title="No score yet, counted as 50">
          50 · no score yet
        </span>
      ) : (
        <div className="flex items-center gap-2">
          <div className="h-1.5 flex-1 rounded-full bg-muted" aria-hidden>
            <div className="h-full rounded-full bg-cobalt" style={{ width: `${value}%` }} />
          </div>
          <span className="tabular w-7 text-right text-label font-semibold">{value}</span>
        </div>
      )}
    </Td>
  )
}

export default function RankingPage() {
  const qc = useQueryClient()
  const rows = useQuery({ queryKey: ['partner-scores', 'ranking'], queryFn: () => adminApi.partnerScores('ranking') })
  const settings = useQuery({ queryKey: ['settings'], queryFn: adminApi.settings })
  const run = useMutation({
    mutationFn: adminApi.runRanking,
    onSuccess: (r) => {
      toast.success(`Ranked ${number(r.partners_scored)} partners.`)
      qc.invalidateQueries({ queryKey: ['partner-scores'] })
      qc.invalidateQueries({ queryKey: ['partners'] })
    },
    onError: (e) => toast.error(errorMessage(e)),
  })

  const weights = settings.data?.find((s) => s.key === 'ranking.weights')?.value
  const ranked = (rows.data || []).filter((r) => r.score !== null).sort((a, b) => b.score - a.score)
  const unranked = (rows.data || []).filter((r) => r.score === null)
  const lastRun = ranked.map((r) => r.calculated_at).sort().pop()

  function exportCsv() {
    downloadCsv(
      'referrai-ranking.csv',
      ranked.map((r, i) => ({
        rank: i + 1,
        partner: r.name,
        email: r.email,
        tier: r.tier_name || '',
        score: r.score.toFixed(1),
        ...Object.fromEntries(RANK_COMPONENTS.map((c) => [c.key, r.contributing_factors?.components?.[c.key] ?? ''])),
      })),
    )
  }

  return (
    <>
      <PageHeader
        title="Partner ranking"
        description={
          weights
            ? `Rank = quality ${weights.quality} · churn resistance ${weights.churn} · volume ${weights.volume} · revenue ${weights.revenue} (relative weights).`
            : 'A weighted mix of quality, churn resistance, volume and revenue.'
        }
        actions={
          <>
            <Button asChild variant="ghost">
              <Link to="/admin/settings">Change weights</Link>
            </Button>
            <Button variant="secondary" onClick={exportCsv} disabled={!ranked.length}>
              <Download />
              Export CSV
            </Button>
            <Button onClick={() => run.mutate()} disabled={run.isPending}>
              {run.isPending ? <Spinner /> : <RefreshCw />}
              Recalculate now
            </Button>
          </>
        }
      />
      <Panel>
        {rows.isLoading ? (
          <LoadingRows rows={8} />
        ) : rows.isError ? (
          <ErrorState error={rows.error} onRetry={rows.refetch} />
        ) : !ranked.length ? (
          <EmptyState
            title="No rankings yet"
            action={
              <Button onClick={() => run.mutate()} disabled={run.isPending}>
                Recalculate now
              </Button>
            }
          >
            Rankings are calculated once a day. Run it now to rank every active partner.
          </EmptyState>
        ) : (
          <>
            <TableWrap>
              <Table>
                <THead>
                  <tr>
                    <Th className="w-12">#</Th>
                    <Th>Partner</Th>
                    <Th>Tier</Th>
                    <Th>Rank score</Th>
                    {RANK_COMPONENTS.map((c) => (
                      <Th key={c.key}>{c.label}</Th>
                    ))}
                  </tr>
                </THead>
                <tbody>
                  {ranked.map((r, i) => (
                    <Tr key={r.partner_id}>
                      <Td>
                        <span
                          className={cn(
                            'tabular grid size-7 place-items-center rounded-full text-label font-semibold',
                            i < 3 ? 'bg-jade text-white' : 'text-muted-text',
                          )}
                        >
                          {i + 1}
                        </span>
                      </Td>
                      <Td className="max-w-[220px]">
                        <Link to={`/admin/partners/${r.partner_id}`} className="block truncate font-semibold text-ink hover:underline">
                          {r.name}
                        </Link>
                        <span className="block truncate text-label text-muted-text">{r.business_name || r.email}</span>
                      </Td>
                      <Td>{r.tier_name ? <Pill tone="grey">{r.tier_name}</Pill> : '—'}</Td>
                      <Td>
                        <ScoreBadge score={r.score} />
                      </Td>
                      {RANK_COMPONENTS.map((c) => (
                        <ComponentCell key={c.key} factors={r.contributing_factors} name={c.key} />
                      ))}
                    </Tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
            <div className="flex flex-wrap justify-between gap-2 border-t border-line px-4 py-3 text-caption text-muted-text">
              <span>
                {number(ranked.length)} ranked
                {unranked.length ? ` · ${number(unranked.length)} not ranked yet (new or suspended)` : ''}
              </span>
              <span>Last calculated {lastRun ? date(lastRun) : '—'}</span>
            </div>
          </>
        )}
      </Panel>
    </>
  )
}
