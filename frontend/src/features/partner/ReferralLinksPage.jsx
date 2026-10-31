// -----------------------------------------------------------------------------
// Referral links and codes. Links redirect visitors to a destination page and
// track the click; codes are generated automatically (no custom codes) and
// credit sales the shop records with the code. Copy and QR for each link.
// -----------------------------------------------------------------------------

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, QrCode } from 'lucide-react'
import QRCode from 'qrcode'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import { CopyButton } from '@/components/app/CopyButton'
import { LedgerStrip } from '@/components/app/LedgerStrip'
import { PageHeader } from '@/components/app/PageHeader'
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
import { partnerApi, referralUrl } from '@/lib/endpoints'
import { date, number, percent } from '@/lib/format'

function NewLinkDialog({ open, onOpenChange }) {
  const qc = useQueryClient()
  const [url, setUrl] = useState('https://')
  const create = useMutation({
    mutationFn: () => partnerApi.createLink(url.trim()),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['links'] })
      toast.success('Link created. Copy it and start sharing.')
      onOpenChange(false)
      setUrl('https://')
    },
  })
  const valid = /^https?:\/\/[^\s.]+\.[^\s]{2,}/.test(url.trim())
  return (
    <Dialog open={open} onOpenChange={(v) => (create.reset(), onOpenChange(v))}>
      <DialogContent title="New referral link" description="Visitors who use the link are sent to this page, and the click is credited to you.">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (valid) create.mutate()
          }}
        >
          <Field label="Destination page" helper="The shop page your link should open, e.g. https://shop.example.com/sale">
            {(p) => <Input {...p} type="url" value={url} onChange={(e) => setUrl(e.target.value)} autoFocus />}
          </Field>
          {create.isError && (
            <Alert variant="error" className="mt-4">
              {errorMessage(create.error)}
            </Alert>
          )}
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!valid || create.isPending}>
              {create.isPending && <Spinner />}
              Create link
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function NewCodeDialog({ open, onOpenChange }) {
  const qc = useQueryClient()
  const create = useMutation({
    mutationFn: partnerApi.createCode,
    onSuccess: (code) => {
      qc.invalidateQueries({ queryKey: ['codes'] })
      toast.success(`Code ${code.code} created.`)
      onOpenChange(false)
    },
  })
  return (
    <Dialog open={open} onOpenChange={(v) => (create.reset(), onOpenChange(v))}>
      <DialogContent title="New referral code" description="We'll create a new code for you. Customers enter it at checkout and the sale is credited to you.">
        {create.isError && <Alert variant="error">{errorMessage(create.error)}</Alert>}
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={() => create.mutate()} disabled={create.isPending}>
            {create.isPending && <Spinner />}
            Create code
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function QrDialog({ link, onOpenChange }) {
  const [src, setSrc] = useState(null)
  const url = link ? referralUrl(link.slug) : ''
  useEffect(() => {
    if (!url) return
    QRCode.toDataURL(url, { width: 480, margin: 2, color: { dark: '#18222F', light: '#FFFFFF' } }).then(setSrc)
  }, [url])
  return (
    <Dialog open={Boolean(link)} onOpenChange={onOpenChange}>
      <DialogContent title="QR code" description={url}>
        <div className="grid place-items-center rounded-[8px] border border-line bg-white p-4">
          {src ? <img src={src} alt={`QR code for ${url}`} className="size-60" /> : <Spinner className="size-6" />}
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          <Button asChild disabled={!src}>
            <a href={src || undefined} download={`referrai-${link?.slug}.png`}>
              Download PNG
            </a>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function ReferralLinksPage() {
  const links = useQuery({ queryKey: ['links'], queryFn: partnerApi.links })
  const codes = useQuery({ queryKey: ['codes'], queryFn: partnerApi.codes })
  const profile = useQuery({ queryKey: ['me', 'partner'], queryFn: partnerApi.profile })
  const [newLink, setNewLink] = useState(false)
  const [newCode, setNewCode] = useState(false)
  const [qrLink, setQrLink] = useState(null)
  const suspended = profile.data && profile.data.status !== 'active'

  const linkList = links.data || []
  const clicks = linkList.reduce((a, l) => a + l.click_count, 0)
  const linkConversions = linkList.reduce((a, l) => a + l.conversion_count, 0)
  const codeConversions = (codes.data || []).reduce((a, c) => a + c.conversion_count, 0)

  return (
    <>
      <PageHeader
        title="Referral links"
        description="Share a link or a code. Every sale it brings in earns you commission."
        actions={
          <Button onClick={() => setNewLink(true)} disabled={suspended}>
            <Plus />
            New link
          </Button>
        }
      />
      {suspended && (
        <Alert variant="warning" className="mb-6">
          Your account is {profile.data.status}, so you can&apos;t create new links or codes right now. Contact an admin if this is unexpected.
        </Alert>
      )}

      <LedgerStrip
        loading={links.isLoading || codes.isLoading}
        items={[
          { label: 'Active links', value: number(linkList.filter((l) => l.is_active).length), context: `${number(codes.data?.length || 0)} codes` },
          { label: 'Link clicks', value: number(clicks), context: 'All time' },
          { label: 'Conversions', value: number(linkConversions + codeConversions), context: `${number(codeConversions)} from codes` },
          { label: 'Link conversion rate', value: clicks ? percent(linkConversions / clicks) : '—', context: 'Sales per click' },
        ]}
      />

      <Panel>
        <PanelHeader title="Links" description="Clicks are counted when someone opens the link." />
        {links.isLoading ? (
          <LoadingRows rows={3} />
        ) : links.isError ? (
          <ErrorState error={links.error} onRetry={links.refetch} />
        ) : !linkList.length ? (
          <EmptyState
            title="No links yet"
            action={
              <Button onClick={() => setNewLink(true)} disabled={suspended}>
                <Plus />
                New link
              </Button>
            }
          >
            Create a link to the page you want to promote, then share it anywhere.
          </EmptyState>
        ) : (
          <TableWrap>
            <Table>
              <THead>
                <tr>
                  <Th>Link</Th>
                  <Th>Destination</Th>
                  <Th num>Clicks</Th>
                  <Th num>Conversions</Th>
                  <Th>Created</Th>
                  <Th>Status</Th>
                  <Th className="text-right">
                    <span className="sr-only">Actions</span>
                  </Th>
                </tr>
              </THead>
              <tbody>
                {linkList.map((l) => (
                  <Tr key={l.id}>
                    <Td className="font-medium whitespace-nowrap">{referralUrl(l.slug).replace(/^https?:\/\//, '')}</Td>
                    <Td className="max-w-[260px]">
                      <span className="block truncate text-muted-text" title={l.destination_url}>
                        {l.destination_url.replace(/^https?:\/\//, '')}
                      </span>
                    </Td>
                    <Td num>{number(l.click_count)}</Td>
                    <Td num>{number(l.conversion_count)}</Td>
                    <Td className="whitespace-nowrap">{date(l.created_at)}</Td>
                    <Td>
                      <StatusPill kind="link" status={l.is_active} />
                    </Td>
                    <Td className="text-right whitespace-nowrap">
                      <CopyButton text={referralUrl(l.slug)} />
                      <Button variant="ghost" size="sm" onClick={() => setQrLink(l)}>
                        <QrCode />
                        QR
                      </Button>
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </TableWrap>
        )}
      </Panel>

      <Panel className="mt-6">
        <PanelHeader
          title="Codes"
          description="Customers enter a code at checkout. Codes are generated for you."
          actions={
            <Button variant="secondary" onClick={() => setNewCode(true)} disabled={suspended}>
              <Plus />
              New code
            </Button>
          }
        />
        {codes.isLoading ? (
          <LoadingRows rows={2} />
        ) : codes.isError ? (
          <ErrorState error={codes.error} onRetry={codes.refetch} />
        ) : !codes.data.length ? (
          <EmptyState title="No codes yet">Create a code for customers to enter at checkout.</EmptyState>
        ) : (
          <TableWrap>
            <Table>
              <THead>
                <tr>
                  <Th>Code</Th>
                  <Th>Created</Th>
                  <Th num>Uses</Th>
                  <Th>Status</Th>
                  <Th className="text-right">
                    <span className="sr-only">Actions</span>
                  </Th>
                </tr>
              </THead>
              <tbody>
                {codes.data.map((c) => (
                  <Tr key={c.id}>
                    <Td className="font-semibold tracking-wide whitespace-nowrap">{c.code}</Td>
                    <Td className="whitespace-nowrap">{date(c.created_at)}</Td>
                    <Td num>{number(c.conversion_count)}</Td>
                    <Td>
                      <StatusPill kind="link" status={c.is_active} />
                    </Td>
                    <Td className="text-right">
                      <CopyButton text={c.code} />
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </TableWrap>
        )}
      </Panel>

      <NewLinkDialog open={newLink} onOpenChange={setNewLink} />
      <NewCodeDialog open={newCode} onOpenChange={setNewCode} />
      <QrDialog link={qrLink} onOpenChange={(v) => !v && setQrLink(null)} />
    </>
  )
}
