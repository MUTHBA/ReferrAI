// Data table primitives: 44px rows, sticky header, hover tint, right-aligned
// numeric cells (<Td num>). Wrap in <TableWrap> so wide tables scroll inside
// their panel instead of the page.
import { cn } from '@/lib/utils'

export function TableWrap({ className, children }) {
  return <div className={cn('w-full overflow-x-auto', className)}>{children}</div>
}

export function Table({ className, children }) {
  return <table className={cn('w-full border-collapse text-caption', className)}>{children}</table>
}

export function THead({ children }) {
  return <thead className="sticky top-0 z-[1] bg-surface">{children}</thead>
}

export function Th({ num, className, children, ...props }) {
  return (
    <th
      scope="col"
      className={cn(
        'h-10 border-b border-line px-4 text-left align-middle text-label font-medium whitespace-nowrap text-muted-text',
        num && 'text-right',
        className,
      )}
      {...props}
    >
      {children}
    </th>
  )
}

export function Tr({ className, onClick, selected, children, ...props }) {
  return (
    <tr
      onClick={onClick}
      className={cn(
        'border-b border-line last:border-b-0 transition-colors duration-100',
        onClick && 'cursor-pointer hover:bg-canvas/70',
        selected && 'bg-jade-soft/60 hover:bg-jade-soft/60',
        className,
      )}
      {...props}
    >
      {children}
    </tr>
  )
}

export function Td({ num, className, children, ...props }) {
  return (
    <td className={cn('h-11 px-4 py-2 align-middle text-text', num && 'tabular text-right whitespace-nowrap', className)} {...props}>
      {children}
    </td>
  )
}

/** Full-width row for "nothing here yet" / loading / error inside a table. */
export function TableMessage({ colSpan, children }) {
  return (
    <tr>
      <td colSpan={colSpan} className="px-4 py-10 text-center text-caption text-muted-text">
        {children}
      </td>
    </tr>
  )
}
