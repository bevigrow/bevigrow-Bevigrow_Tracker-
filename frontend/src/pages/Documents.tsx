import { FileUp } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { Button, Card, EmptyState, Select, Skeleton } from '../components/ui'
import { api } from '../lib/api'
import { DOC_TYPE_LABEL } from '../lib/format'
import { useToast } from '../lib/toast'
import type { Contact, DocType, DocumentFile } from '../lib/types'
import { DocumentList, UploadModal } from './ContactDetail'

export function Documents() {
  const toast = useToast()
  const [documents, setDocuments] = useState<DocumentFile[]>([])
  const [contacts, setContacts] = useState<Contact[]>([])
  const [loading, setLoading] = useState(true)
  const [docType, setDocType] = useState('')
  const [contactId, setContactId] = useState('')
  const [uploadOpen, setUploadOpen] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setDocuments(
        await api.listDocuments({
          doc_type: docType || undefined,
          contact_id: contactId || undefined,
        }),
      )
    } catch {
      toast.error('Could not load documents.')
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [docType, contactId])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    api.listContacts().then(setContacts).catch(() => setContacts([]))
  }, [])

  const companyFor = (id: number) => contacts.find((c) => c.id === id)?.company_name

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl text-latte">Documents &amp; Proof</h1>
          <p className="mt-1 text-sm text-latte/50">
            {loading ? 'Loading…' : `${documents.length} file${documents.length === 1 ? '' : 's'}`}
          </p>
        </div>
        <Button
          onClick={() => setUploadOpen(true)}
          disabled={!contacts.length}
          icon={<FileUp size={15} />}
        >
          Upload
        </Button>
      </div>

      <Card className="!p-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <Select
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
            options={[
              { value: '', label: 'All document types' },
              ...(Object.keys(DOC_TYPE_LABEL) as DocType[]).map((t) => ({
                value: t,
                label: DOC_TYPE_LABEL[t],
              })),
            ]}
          />
          <Select
            value={contactId}
            onChange={(e) => setContactId(e.target.value)}
            options={[
              { value: '', label: 'All accounts' },
              ...contacts.map((c) => ({ value: String(c.id), label: c.company_name })),
            ]}
          />
        </div>
      </Card>

      {loading ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : documents.length === 0 ? (
        <EmptyState
          emoji="📄"
          title="No proof on file yet"
          hint="Upload quotations, invoices, purchase orders, screenshots or sample photos from an account page."
        />
      ) : (
        <Card>
          <DocumentList
            documents={documents.map((d) => ({
              ...d,
              note: d.note ?? (companyFor(d.contact_id) ? `${companyFor(d.contact_id)}` : null),
            }))}
            onDeleted={(id) => setDocuments((list) => list.filter((d) => d.id !== id))}
          />
        </Card>
      )}

      <UploadModal
        open={uploadOpen}
        contacts={contacts}
        onClose={() => setUploadOpen(false)}
        onUploaded={() => {
          setUploadOpen(false)
          void load()
        }}
      />
    </div>
  )
}
