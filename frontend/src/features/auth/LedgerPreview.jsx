// -----------------------------------------------------------------------------
// Decorative ledger shown on the auth screens (from the Stitch design): three
// example ledger rows illustrating what ReferrAI tracks. Static sample data —
// marked aria-hidden so screen readers skip it.
// -----------------------------------------------------------------------------

const ROWS = [
  { name: 'Peak Fitness Coaching', detail: 'Sale $240.00', amount: '+$24.00', kind: 'Commission' },
  { name: 'UrbanThreads', detail: 'Sale $89.50', amount: '+$8.95', kind: 'Commission' },
  { name: 'Northwind Travel', detail: 'Withdrawal paid', amount: '−$150.00', kind: 'Payout' },
]

export function LedgerPreview() {
  return (
    <div className="w-full max-w-md" aria-hidden="true">
      <h2 className="text-title font-semibold tracking-tight text-white">Track every referral from click to payout.</h2>
      <p className="mt-2 text-body text-white/60">Clicks, sales, commissions and withdrawals in one ledger.</p>

      <div className="mt-8 overflow-hidden rounded-[8px] border border-white/10 bg-black/20">
        <div className="flex items-center justify-between border-b border-white/10 px-4 py-2.5 text-caption text-white/50">
          <span>Activity</span>
          <span>Amount</span>
        </div>
        {ROWS.map((row, i) => (
          <div
            key={row.name}
            className={`flex items-center justify-between px-4 py-3 ${i < ROWS.length - 1 ? 'border-b border-white/10' : ''}`}
          >
            <div className="min-w-0">
              <div className="truncate font-semibold text-white">{row.name}</div>
              <div className="tabular text-caption text-white/50">{row.detail}</div>
            </div>
            <div className="text-right">
              <div
                className={`tabular font-semibold ${row.kind === 'Payout' ? 'text-[#F2A99F]' : 'text-jade-bright'}`}
              >
                {row.amount}
              </div>
              <div className="text-label text-white/50">{row.kind}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
