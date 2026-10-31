// shadcn/ui Button, restyled to the ReferrAI tokens (6px radius, no shadows).
import { Slot } from '@radix-ui/react-slot'
import { cva } from 'class-variance-authority'
import { forwardRef } from 'react'

import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[6px] text-body font-semibold transition-colors duration-150 cursor-pointer disabled:pointer-events-none disabled:opacity-55 [&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        primary: 'bg-jade text-white hover:bg-jade-strong',
        secondary: 'border border-line bg-surface text-ink hover:bg-canvas',
        destructive: 'bg-rose text-white hover:opacity-90',
        ghost: 'text-ink hover:bg-canvas',
        link: 'h-auto px-0 text-jade underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-9 px-4',
        sm: 'h-8 px-3 text-caption',
        lg: 'h-10 px-5',
        icon: 'size-9',
      },
    },
    defaultVariants: { variant: 'primary', size: 'default' },
  },
)

const Button = forwardRef(function Button({ className, variant, size, asChild = false, ...props }, ref) {
  const Comp = asChild ? Slot : 'button'
  return <Comp ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
})

export { Button, buttonVariants }
