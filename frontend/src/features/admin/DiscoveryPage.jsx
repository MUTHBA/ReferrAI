// -----------------------------------------------------------------------------
// Partner discovery: score a business you might invite against your best
// current partners (those with revenue). Potential = 70% text similarity to
// the closest top partners + 30% category fit (share of partner revenue in the
// same category). Track each candidate: invite, mark reviewed or dismiss.
// -----------------------------------------------------------------------------

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Info, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { LedgerStrip } from '@/components/app/LedgerStrip'
import { PageHeader } from '@/components/app/PageHeader'
import { ScoreBadge } from '@/components/app/ScoreBadge'
import { EmptyState, ErrorState, LoadingRows } from '@/components/app/States'
import { WhyBars } from '@/components/app/WhyBars'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Panel, PanelHeader } from '@/components/ui/panel'
import { StatusPill } from '@/components/ui/pill'
import { Segmented } from '@/components/ui/segmented'
import { Select } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import { Table, TableMessage, TableWrap, Td, Th, THead, Tr } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { CATEGORIES } from '@/features/auth/RegisterPage'
import { errorMessage } from '@/lib/api'
import { adminApi } from '@/lib/endpoints'
import { number } from '@/lib/format'

function factorsFor(c) {
  const f = c.score_factors || {}
  if (f.similarity === null || f.similarity === undefined) return []
  const w = f.weights || { similarity: 0.7, category_fit: 0.3 }
  return [
    { label: 'similar to your top partners', effect: 100 * w.similarity * f.similarity },
    { label: 'category fit', effect: 100 * w.category_fit * (f.category_fit || 0) },
  ]
}

function ScoreForm() {
  const qc = useQueryClient()
  const [form, setForm] = useState({ business_name: '', category: '', description: '' })
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const score = useMutation({
    mutationFn: () => adminApi.scoreCandidates([{ business_name: form.business_name.trim(), category: form.category, description: form.description.trim() }]),
    onSuccess: ([c]) => {
      qc.invalidateQueries({ queryKey: ['candidates'] })
      toast.success(
        c.potential_score === null ? `${c.candidate_name} saved. Add partners with sales to score candidates.` : `${c.candidate_name} scored ${Math.round(c.potential_score)}/100.`,
      )
      setForm({ business_name: '', category: '', description: '' })
    },
  })
  const valid = form.business_name.trim() && form.category && form.description.trim().length >= 10

  return (
    <Panel className="mb-6">
      <PanelHeader title="Score a candidate" description="Describe a business you might invite. It's compared with your best current partners." />
      <form
        className="space-y-4 p-5"
        onSubmit={(e) => {
          e.preventDefault()
          if (valid) score.mutate()
        }}
      >
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Business name">{(p) => <Input {...p} value={form.business_name} onChange={set('business_name')} placeholder="e.g. Kura Athletics" maxLength={255} />}</Field>
          <Field label="Category">
            {(p) => (
              <Select {...p} value={form.category} onChange={set('category')}>
                <option value="">Select a category…</option>
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>
        <Field label="Description" helper="What they sell and who to — a sentence or two works best.">
          {(p) => (
            <Textarea {...p} rows={2} value={form.description} onChange={set('description')} placeholder="Yoga and pilates studio selling class packs and activewear to young professionals." />
          )}
        </Field>
        {score.isError && <Alert variant="error">{errorMessage(score.error)}</Alert>}
        <div className="flex justify-end">
          <Button type="submit" disabled={!valid || score.isPending}>
            {score.isPending ? <Spinner /> : <Sparkles />}
            Score candidate
          </Button>
        </div>
      </form>
    </Panel>
  )
}

export default function DiscoveryPage() {
  const qc = useQueryClient()
  const list = useQuery({ queryKey: ['candidates'], queryFn: () => adminApi.candidates() })
  const [tab, setTab] = useState('')
  const update = useMutation({
    mutationFn: ({ id, status }) => adminApi.updateCandidate(id, status),
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ['candidates'] })
      toast.success(`${c.candidate_name} marked ${c.status}.`)
    },
    onError: (e) => toast.error(errorMessage(e)),
  })

  const all = list.data || []
  const count = (s) => all.filter((c) => c.status === s).length
  const shown = all.filter((c) => !tab || c.status === tab).sort((a, b) => (b.potential_score ?? -1) - (a.potential_score ?? -1))
  const scored = all.filter((c) => c.potential_score !== null)
  const avg = scored.length ? scored.reduce((a, c) => a + Number(c.potential_score), 0) / scored.length : null

  return (
    <>
      <PageHeader title="Partner discovery" description="Find businesses that look like your best partners." />
      <LedgerStrip
        loading={list.isLoading}
        items={[
          { label: 'Candidates', value: number(all.length), context: `${number(count('reviewed'))} reviewed` },
          { label: 'New', value: number(count('new')), tone: count('new') ? 'cobalt' : 'default', context: 'Not looked at yet' },
          { label: 'Invited', value: number(count('invited')), tone: 'jade', context: `${number(count('dismissed'))} dismissed` },
          { label: 'Average potential', value: avg === null ? '—' : `${Math.round(avg)}/100`, context: 'Across scored candidates' },
        ]}
      />
      <ScoreForm />
      <Panel>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
          <h2 className="text-section font-semibold text-ink">Candidates</h2>
          <Segmented
            size="sm"
            label="Candidate status"
            value={tab}
            onChange={setTab}
            options={[
              { value: '', label: 'All', count: all.length },
              { value: 'new', label: 'New', count: count('new') },
              { value: 'reviewed', label: 'Reviewed', count: count('reviewed') },
              { value: 'invited', label: 'Invited', count: count('invited') },
              { value: 'dismissed', label: 'Dismissed', count: count('dismissed') },
            ]}
          />
        </div>
        {list.isLoading ? (
          <LoadingRows rows={4} />
        ) : list.isError ? (
          <ErrorState error={list.error} onRetry={list.refetch} />
        ) : !all.length ? (
          <EmptyState title="No candidates yet">Score a business above to see how closely it matches your best partners.</EmptyState>
        ) : (
          <TableWrap>
            <Table>
              <THead>
                <tr>
                  <Th>Business</Th>
                  <Th>Category</Th>
                  <Th>Potential</Th>
                  <Th className="min-w-56">Why</Th>
                  <Th>Most similar to</Th>
                  <Th>Status</Th>
                  <Th>
                    <span className="sr-only">Actions</span>
                  </Th>
                </tr>
              </THead>
              <tbody>
                {!shown.length && <TableMessage colSpan={7}>No candidates with this status.</TableMessage>}
                {shown.map((c) => (
                  <Tr key={c.id}>
                    <Td className="max-w-[200px]">
                      <div className="font-semibold text-ink">{c.candidate_name}</div>
                      {c.raw_data?.description && (
                        <div className="line-clamp-2 text-label text-muted-text" title={c.raw_data.description}>
                          {c.raw_data.description}
                        </div>
                      )}
                    </Td>
                    <Td className="whitespace-nowrap">{c.business_category || '—'}</Td>
                    <Td>
                      <ScoreBadge score={c.potential_score} pendingLabel="Not scored" />
                    </Td>
                    <Td className="py-3">
                      {c.potential_score === null ? (
                        <span className="text-label text-muted-text">{c.score_factors?.note || 'Not scored.'}</span>
                      ) : (
                        <WhyBars factors={factorsFor(c)} max={70} compact />
                      )}
                    </Td>
                    <Td className="max-w-[180px] text-caption">
                      {(c.score_factors?.closest_partners || []).length ? (c.score_factors.closest_partners || []).join(', ') : '—'}
                    </Td>
                    <Td>
                      <StatusPill kind="candidate" status={c.status} />
                    </Td>
                    <Td className="text-right whitespace-nowrap">
                      {c.status !== 'invited' && (
                        <Button size="sm" onClick={() => update.mutate({ id: c.id, status: 'invited' })} disabled={update.isPending}>
                          Invite
                        </Button>
                      )}
                      {c.status === 'new' && (
                        <Button size="sm" variant="ghost" className="ml-1" onClick={() => update.mutate({ id: c.id, status: 'reviewed' })} disabled={update.isPending}>
                          Mark reviewed
                        </Button>
                      )}
                      {c.status !== 'dismissed' && c.status !== 'invited' && (
                        <Button size="sm" variant="ghost" className="ml-1 text-muted-text" onClick={() => update.mutate({ id: c.id, status: 'dismissed' })} disabled={update.isPending}>
                          Dismiss
                        </Button>
                      )}
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </TableWrap>
        )}
      </Panel>
      <p className="mt-3 flex items-center gap-2 text-label text-muted-text">
        <Info className="size-3.5 shrink-0" aria-hidden />
        Candidates are compared with active partners who already have sales. &ldquo;Invite&rdquo; records your decision; send the invitation yourself.
      </p>
    </>
  )
}
