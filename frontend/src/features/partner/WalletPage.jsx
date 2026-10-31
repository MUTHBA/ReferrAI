// -----------------------------------------------------------------------------
// Wallet: balance, withdrawals and every balance movement. Requesting a
// withdrawal holds the money straight away; requests under the auto-approve
// threshold are approved automatically (unless there is an open fraud alert),
// larger ones are reviewed by an admin, who then pays it outside ReferrAI and
// marks it paid. A rejected request returns the money to the wallet.
// -----------------------------------------------------------------------------

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Banknote } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { LedgerStrip } from '@/components/app/LedgerStrip'
import { PageHeader } from '@/components/app/PageHeader'
import { paginate, Pagination } from '@/components/app/Pagination'
import { EmptyState, ErrorState, LoadingRows } from '@/components/app/States'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter } from '@/components/ui/dialog'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Panel, PanelHeader } from '@/components/ui/panel'
import { StatusPill } from '@/components/ui/pill'
import { Spinner } from '@/components/ui/spinner'
import { Table, TableWrap, Td, Th, THead, Tr } from '@/components/ui/table'
import { errorMessage } from '@/lib/api'
import { partnerApi } from '@/lib/endpoints'
import { date, dateTime, money, number, signedMoney, toNumber } from '@/lib/format'
import { cn } from '@/lib/utils'

const TX_PAGE = 15

function WithdrawDialog({ open, onOpenChange, wallet }) {
  const qc = useQueryClient()
  const [amount, setAmount] = useState('')
  const balance = toNumber(wallet?.balance) || 0
  const min = toNumber(wallet?.min_withdrawal_amount) ?? 10
  const auto = toNumber(wallet?.auto_approval_threshold) ?? 100
  const value = toNumber(amount)
  let problem = null
  if (amount && (value === null || value <= 0)) problem = 'Enter an amount in dollars, e.g. 50 or 50.25.'
  else if (value !== null && value < min) problem = `The minimum withdrawal is ${money(min)}.`
  else if (value !== null && value > balance) problem = `You can withdraw up to ${money(balance)}.`
  else if (amount && !/^\d+(\.\d{1,2})?$/.test(amount.trim())) problem = 'Use at most two decimal places.'

  const request = useMutation({
    mutationFn: () => partnerApi.requestWithdrawal(amount.trim()),
    onSuccess: (w) => {
      qc.invalidateQueries({ queryKey: ['wallet'] })
      qc.invalidateQueries({ queryKey: ['my-withdrawals'] })
      qc.invalidateQueries({ queryKey: ['transactions'] })
      qc.invalidateQueries({ queryKey: ['partner-dashboard'] })
      toast.success(
        w.status === 'approved'
          ? `${money(w.amount)} approved automatically. An admin will send it to you.`
          : `${money(w.amount)} requested. An admin will review it.`,
      )
      setAmount('')
      onOpenChange(false)
    },
  })

  return (
    <Dialog open={open} onOpenChange={(v) => (request.reset(), onOpenChange(v))}>
      <DialogContent
        title="Request a withdrawal"
        description={`Available: ${money(balance)}. The amount is held from your balance while the request is open.`}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (!problem && value) request.mutate()
          }}
        >
          <Field
            label="Amount ($)"
            error={problem}
            helper={`Minimum ${money(min)}. Requests under ${money(auto)} are approved automatically; larger ones are reviewed by an admin.`}
          >
            {(p) => (
              <Input {...p} inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="0.00" autoFocus />
            )}
          </Field>
          <button type="button" className="mt-2 text-caption text-jade hover:underline" onClick={() => setAmount(balance.toFixed(2))}>
            Withdraw everything ({money(balance)})
          </button>
          {request.isError && (
            <Alert variant="error" className="mt-4">
              {errorMessage(request.error)}
            </Alert>
          )}
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!value || Boolean(problem) || request.isPending}>
              {request.isPending && <Spinner />}
              Request {value && !problem ? money(value) : 'withdrawal'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function withdrawalNote(w) {
  if (w.notes) return w.notes
  if (w.status === 'pending') return 'Waiting for admin review'
  if (w.status === 'approved') return w.requires_manual_review ? 'Approved, payment on its way' : 'Approved automatically, payment on its way'
  if (w.status === 'paid') return 'Paid to you'
  if (w.status === 'rejected') return 'Money returned to your wallet'
  return ''
}

export default function WalletPage() {
  const wallet = useQuery({ queryKey: ['wallet'], queryFn: partnerApi.wallet })
  const withdrawals = useQuery({ queryKey: ['my-withdrawals'], queryFn: partnerApi.withdrawals })
  const transactions = useQuery({ queryKey: ['transactions'], queryFn: partnerApi.transactions })
  const profile = useQuery({ queryKey: ['me', 'partner'], queryFn: partnerApi.profile })
  const [open, setOpen] = useState(false)
  const [txOffset, setTxOffset] = useState(0)
  const w = wallet.data
  const pendingCount = (withdrawals.data || []).filter((x) => x.status === 'pending').length
  const suspended = profile.data && profile.data.status !== 'active'
  const canWithdraw = w && !suspended && toNumber(w.balance) >= (toNumber(w.min_withdrawal_amount) ?? 10)

  return (
    <>
      <PageHeader
        title="Wallet"
        description="Your balance, withdrawals and every movement of money."
        actions={
          <Button onClick={() => setOpen(true)} disabled={!canWithdraw}>
            <Banknote />
            Withdraw
          </Button>
        }
      />
      {suspended && (
        <Alert variant="warning" className="mb-6">
          Your account is {profile.data.status}, so withdrawals are paused. Contact an admin if this is unexpected.
        </Alert>
      )}
      {wallet.isError ? (
        <Panel className="mb-6">
          <ErrorState error={wallet.error} onRetry={wallet.refetch} />
        </Panel>
      ) : (
        <LedgerStrip
          loading={wallet.isLoading}
          items={[
            { label: 'Available balance', value: money(w?.balance), tone: 'jade', context: canWithdraw ? 'Ready to withdraw' : `Minimum withdrawal ${money(w?.min_withdrawal_amount)}` },
            {
              label: 'Pending withdrawals',
              value: money(w?.pending_withdrawals),
              tone: toNumber(w?.pending_withdrawals) ? 'amber' : 'default',
              context: pendingCount ? `${number(pendingCount)} ${pendingCount === 1 ? 'request' : 'requests'} in review` : 'None in review',
            },
            { label: 'Total withdrawn', value: money(w?.total_withdrawn), context: `${money(w?.total_earned)} earned all time` },
          ]}
        />
      )}

      <Panel>
        <PanelHeader title="Withdrawals" description="Requests you've made and where each one is." />
        {withdrawals.isLoading ? (
          <LoadingRows rows={3} />
        ) : withdrawals.isError ? (
          <ErrorState error={withdrawals.error} onRetry={withdrawals.refetch} />
        ) : !withdrawals.data.length ? (
          <EmptyState title="No withdrawals yet">When you request a withdrawal it appears here until it&apos;s paid.</EmptyState>
        ) : (
          <TableWrap>
            <Table>
              <THead>
                <tr>
                  <Th>Requested</Th>
                  <Th num>Amount</Th>
                  <Th>Status</Th>
                  <Th>Note</Th>
                  <Th>Updated</Th>
                </tr>
              </THead>
              <tbody>
                {withdrawals.data.map((x) => (
                  <Tr key={x.id}>
                    <Td className="whitespace-nowrap">{date(x.requested_at)}</Td>
                    <Td num className="font-semibold">
                      {money(x.amount)}
                    </Td>
                    <Td>
                      <StatusPill kind="withdrawal" status={x.status} />
                    </Td>
                    <Td className={cn('min-w-48', x.status === 'rejected' ? 'text-rose' : 'text-muted-text')}>{withdrawalNote(x)}</Td>
                    <Td className="whitespace-nowrap text-muted-text">{x.reviewed_at ? date(x.reviewed_at) : '—'}</Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </TableWrap>
        )}
      </Panel>

      <Panel className="mt-6">
        <PanelHeader title="Transactions" description="Every change to your balance, newest first." />
        {transactions.isLoading ? (
          <LoadingRows rows={5} />
        ) : transactions.isError ? (
          <ErrorState error={transactions.error} onRetry={transactions.refetch} />
        ) : !transactions.data.length ? (
          <EmptyState title="No transactions yet">Commissions and withdrawals appear here.</EmptyState>
        ) : (
          <>
            <TableWrap>
              <Table>
                <THead>
                  <tr>
                    <Th>Date</Th>
                    <Th>Description</Th>
                    <Th num>Amount</Th>
                    <Th num>Balance after</Th>
                  </tr>
                </THead>
                <tbody>
                  {paginate(transactions.data, txOffset, TX_PAGE).map((t) => {
                    const n = toNumber(t.amount) || 0
                    return (
                      <Tr key={t.id}>
                        <Td className="whitespace-nowrap">{dateTime(t.created_at)}</Td>
                        <Td className="min-w-56">{t.description || t.reference_type}</Td>
                        <Td num className={cn('font-semibold', n < 0 ? 'text-rose' : 'text-jade')}>
                          {signedMoney(n)}
                        </Td>
                        <Td num>{money(t.balance_after)}</Td>
                      </Tr>
                    )
                  })}
                </tbody>
              </Table>
            </TableWrap>
            <Pagination offset={txOffset} limit={TX_PAGE} total={transactions.data.length} onChange={setTxOffset} noun="transactions" />
          </>
        )}
      </Panel>

      <WithdrawDialog open={open} onOpenChange={setOpen} wallet={w} />
    </>
  )
}
