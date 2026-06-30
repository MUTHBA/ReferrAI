// -----------------------------------------------------------------------------
// frontend/src/pages/partner/WalletPage.jsx
//
// Partner wallet page (WAL-005). Shows balance, total earned, total withdrawn,
// a full transaction history table, and a withdrawal request form. The form
// validates that the amount is a positive number before submitting; server-side
// errors (below minimum, insufficient balance) are surfaced inline via the
// error state rather than a global handler.
// -----------------------------------------------------------------------------

import { useEffect, useState } from 'react'
import {
  extractErrorMessage,
  getTransactions,
  getWallet,
  requestWithdrawal,
} from '../../api/walletApi.js'

const styles = {
  cards: {
    display: 'flex',
    gap: '16px',
    marginBottom: '32px',
    flexWrap: 'wrap',
  },
  card: {
    flex: '1 1 160px',
    padding: '20px',
    borderRadius: '8px',
    backgroundColor: '#ffffff',
    border: '1px solid #e5e7eb',
  },
  cardLabel: { fontSize: '13px', color: '#6b7280', margin: '0 0 6px' },
  cardValue: { fontSize: '28px', fontWeight: 700, margin: 0 },
  section: { marginBottom: '32px' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '14px' },
  th: {
    textAlign: 'left',
    padding: '10px 12px',
    borderBottom: '2px solid #e5e7eb',
    color: '#374151',
    fontWeight: 600,
  },
  td: { padding: '10px 12px', borderBottom: '1px solid #f3f4f6' },
  form: { display: 'flex', gap: '12px', alignItems: 'flex-end', flexWrap: 'wrap' },
  input: {
    padding: '8px 10px',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    width: '160px',
  },
  button: {
    padding: '9px 20px',
    borderRadius: '6px',
    border: 'none',
    backgroundColor: '#2563eb',
    color: '#fff',
    fontWeight: 600,
    cursor: 'pointer',
  },
  error: { color: '#b91c1c', fontSize: '14px', marginTop: '8px' },
  success: { color: '#15803d', fontSize: '14px', marginTop: '8px' },
  debit: { color: '#b91c1c' },
  credit: { color: '#15803d' },
}

function fmt(amount) {
  return `$${Number(amount).toFixed(2)}`
}

export default function WalletPage() {
  const [wallet, setWallet] = useState(null)
  const [transactions, setTransactions] = useState([])
  const [loading, setLoading] = useState(true)
  const [amount, setAmount] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  async function load() {
    try {
      const [w, t] = await Promise.all([getWallet(), getTransactions()])
      setWallet(w)
      setTransactions(t)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function handleWithdraw(event) {
    event.preventDefault()
    setError('')
    setSuccess('')
    setSubmitting(true)
    try {
      const withdrawal = await requestWithdrawal(Number(amount))
      setSuccess(
        withdrawal.status === 'approved'
          ? `Withdrawal of ${fmt(withdrawal.amount)} approved automatically.`
          : `Withdrawal of ${fmt(withdrawal.amount)} submitted for admin review.`,
      )
      setAmount('')
      load()
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <p>Loading…</p>

  return (
    <section>
      <h1>Wallet</h1>

      <div style={styles.cards}>
        <div style={styles.card}>
          <p style={styles.cardLabel}>Available Balance</p>
          <p style={styles.cardValue}>{fmt(wallet?.balance ?? 0)}</p>
        </div>
        <div style={styles.card}>
          <p style={styles.cardLabel}>Total Earned</p>
          <p style={styles.cardValue}>{fmt(wallet?.total_earned ?? 0)}</p>
        </div>
        <div style={styles.card}>
          <p style={styles.cardLabel}>Total Withdrawn</p>
          <p style={styles.cardValue}>{fmt(wallet?.total_withdrawn ?? 0)}</p>
        </div>
      </div>

      <div style={styles.section}>
        <h2>Request Withdrawal</h2>
        <form style={styles.form} onSubmit={handleWithdraw}>
          <input
            style={styles.input}
            type="number"
            min="0.01"
            step="0.01"
            placeholder="Amount"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            required
          />
          <button style={styles.button} type="submit" disabled={submitting}>
            {submitting ? 'Submitting…' : 'Withdraw'}
          </button>
        </form>
        {error && <p style={styles.error}>{error}</p>}
        {success && <p style={styles.success}>{success}</p>}
      </div>

      <div style={styles.section}>
        <h2>Transaction History</h2>
        {transactions.length === 0 ? (
          <p>No transactions yet.</p>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Date</th>
                <th style={styles.th}>Type</th>
                <th style={styles.th}>Amount</th>
                <th style={styles.th}>Balance After</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((tx) => (
                <tr key={tx.id}>
                  <td style={styles.td}>{new Date(tx.created_at).toLocaleDateString()}</td>
                  <td style={styles.td}>{tx.reference_type}</td>
                  <td style={{ ...styles.td, ...(tx.amount < 0 ? styles.debit : styles.credit) }}>
                    {tx.amount < 0 ? '-' : '+'}{fmt(Math.abs(tx.amount))}
                  </td>
                  <td style={styles.td}>{fmt(tx.balance_after)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}
