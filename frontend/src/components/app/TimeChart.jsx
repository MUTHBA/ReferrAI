// -----------------------------------------------------------------------------
// frontend/src/components/app/TimeChart.jsx
//
// Daily time-series chart (recharts) following the dataviz rules:
//   - one y-axis only; series must share a unit (money with money, counts
//     with counts) — different units go in separate charts
//   - area (jade fill ~12%) for money, thin rounded bars for counts
//   - legend above the plot for 2+ series (the title names a single series)
//   - crosshair tooltip listing every series at that day, value first
//   - recessive grid, and a "Table" toggle so values are reachable without hover
// series: [{ key, label, color: 'var(--chart-1)' }]
// -----------------------------------------------------------------------------

import { useState } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { Table, TableWrap, Td, Th, THead, Tr } from '@/components/ui/table'
import { shortDate, toNumber } from '@/lib/format'
import { cn } from '@/lib/utils'

function ChartTooltip({ active, payload, label, series, format }) {
  if (!active || !payload?.length) return null
  return (
    <div className="min-w-36 rounded-[8px] border border-line bg-surface px-3 py-2 shadow-lg">
      <div className="mb-1.5 text-label text-muted-text">{shortDate(label)}</div>
      {series.map((s) => {
        const p = payload.find((x) => x.dataKey === s.key)
        return (
          <div key={s.key} className="flex items-center gap-2 py-0.5">
            <span className="h-0.5 w-3 rounded-full" style={{ background: s.color }} aria-hidden />
            <span className="tabular text-caption font-semibold text-ink">{format(p?.value)}</span>
            <span className="text-label text-muted-text">{s.label}</span>
          </div>
        )
      })}
    </div>
  )
}

function Legend({ series, kind }) {
  if (series.length < 2) return null
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1">
      {series.map((s) => (
        <span key={s.key} className="inline-flex items-center gap-1.5 text-label text-muted-text">
          <span
            className={cn(kind === 'area' ? 'h-0.5 w-3 rounded-full' : 'size-2.5 rounded-[2px]')}
            style={{ background: s.color }}
            aria-hidden
          />
          {s.label}
        </span>
      ))}
    </div>
  )
}

export function TimeChart({ data, series, kind = 'area', format = (v) => v, axisFormat, height = 240, className }) {
  const [asTable, setAsTable] = useState(false)
  const rows = (data || []).map((d) => {
    const row = { date: d.date }
    series.forEach((s) => {
      row[s.key] = toNumber(d[s.key]) ?? 0
    })
    return row
  })
  const tickFormat = axisFormat || format
  const common = {
    data: rows,
    margin: { top: 8, right: 8, bottom: 0, left: 0 },
  }
  const axes = (
    <>
      <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
      <XAxis
        dataKey="date"
        tickFormatter={shortDate}
        tick={{ fontSize: 12, fill: 'var(--muted-text)' }}
        tickLine={false}
        axisLine={{ stroke: 'var(--line)' }}
        minTickGap={28}
      />
      <YAxis
        tickFormatter={tickFormat}
        tick={{ fontSize: 12, fill: 'var(--muted-text)' }}
        tickLine={false}
        axisLine={false}
        width={64}
        allowDecimals={false}
      />
      <Tooltip
        content={<ChartTooltip series={series} format={format} />}
        cursor={kind === 'area' ? { stroke: 'var(--muted-text)', strokeWidth: 1 } : { fill: 'var(--muted)', opacity: 0.6 }}
      />
    </>
  )

  return (
    <div className={className}>
      <div className="mb-3 flex items-center justify-between gap-3">
        <Legend series={series} kind={kind} />
        <button
          type="button"
          onClick={() => setAsTable((v) => !v)}
          className="ml-auto text-label text-muted-text underline-offset-4 hover:text-ink hover:underline"
        >
          {asTable ? 'Chart' : 'Table'}
        </button>
      </div>
      {asTable ? (
        <TableWrap className="max-h-[260px] overflow-y-auto rounded-[6px] border border-line">
          <Table>
            <THead>
              <tr>
                <Th>Date</Th>
                {series.map((s) => (
                  <Th key={s.key} num>
                    {s.label}
                  </Th>
                ))}
              </tr>
            </THead>
            <tbody>
              {[...rows].reverse().map((r) => (
                <Tr key={r.date}>
                  <Td>{shortDate(r.date)}</Td>
                  {series.map((s) => (
                    <Td key={s.key} num>
                      {format(r[s.key])}
                    </Td>
                  ))}
                </Tr>
              ))}
            </tbody>
          </Table>
        </TableWrap>
      ) : (
        <div style={{ height }} role="img" aria-label={`${series.map((s) => s.label).join(' and ')} per day`}>
          <ResponsiveContainer width="100%" height="100%">
            {kind === 'area' ? (
              <AreaChart {...common}>
                <defs>
                  {series.map((s) => (
                    <linearGradient key={s.key} id={`fill-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={s.color} stopOpacity={0.14} />
                      <stop offset="100%" stopColor={s.color} stopOpacity={0.02} />
                    </linearGradient>
                  ))}
                </defs>
                {axes}
                {series.map((s) => (
                  <Area
                    key={s.key}
                    type="monotone"
                    dataKey={s.key}
                    stroke={s.color}
                    strokeWidth={2}
                    fill={`url(#fill-${s.key})`}
                    activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--surface)' }}
                    isAnimationActive={false}
                  />
                ))}
              </AreaChart>
            ) : (
              <BarChart {...common} barGap={2} barCategoryGap="20%">
                {axes}
                {series.map((s) => (
                  <Bar key={s.key} dataKey={s.key} fill={s.color} radius={[4, 4, 0, 0]} maxBarSize={18} isAnimationActive={false} />
                ))}
              </BarChart>
            )}
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

/** Compact money ticks: $1.2k, $15k. */
export function compactMoney(value) {
  const n = toNumber(value) || 0
  if (Math.abs(n) >= 1000) return `$${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k`
  return `$${Math.round(n)}`
}

export function compactNumber(value) {
  const n = toNumber(value) || 0
  if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k`
  return String(Math.round(n))
}
