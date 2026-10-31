// "Showing 1–25 of 86" with Previous / Next.
import { Button } from '@/components/ui/button'
import { number } from '@/lib/format'

export function Pagination({ offset, limit, total, onChange, noun = 'rows' }) {
  if (!total) return null
  const from = offset + 1
  const to = Math.min(offset + limit, total)
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3">
      <span className="tabular text-caption text-muted-text">
        Showing {number(from)}–{number(to)} of {number(total)} {noun}
      </span>
      <div className="flex gap-2">
        <Button variant="secondary" size="sm" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>
          Previous
        </Button>
        <Button variant="secondary" size="sm" disabled={to >= total} onClick={() => onChange(offset + limit)}>
          Next
        </Button>
      </div>
    </div>
  )
}

/** Client-side paging helper for lists the API returns whole. */
export function paginate(list, offset, limit) {
  return list.slice(offset, offset + limit)
}
