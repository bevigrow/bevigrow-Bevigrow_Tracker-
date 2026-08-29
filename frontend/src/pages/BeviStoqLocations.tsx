import { Trash2, Edit2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { request } from '../lib/api'
import { Button, Card, Input, Field, Modal, Spinner, EmptyState, ConfirmDialog } from '../components/ui'

interface Location {
  id: number
  name: string
  description?: string
  active: boolean
  created_at: string
}

export function BeviStoqLocations() {
  const [locations, setLocations] = useState<Location[]>([])
  const [loading, setLoading] = useState(true)
  const [isCreating, setIsCreating] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)

  const [formData, setFormData] = useState({ name: '', description: '' })
  const [error, setError] = useState<string>('')

  useEffect(() => {
    load()
  }, [])

  const load = async () => {
    try {
      setLoading(true)
      const data = await request<Location[]>('/api/bevi-stoq/locations?active_only=true&limit=1000')
      setLocations(data)
    } catch (error) {
      console.error('Load error:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    try {
      setError('')
      if (!formData.name || !formData.name.trim()) {
        setError('Location Name is required')
        return
      }

      const payload = { name: formData.name, description: formData.description }

      if (isEditing && editingId) {
        await request(`/api/bevi-stoq/locations/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify(payload)
        })
      } else {
        await request('/api/bevi-stoq/locations', {
          method: 'POST',
          body: JSON.stringify(payload)
        })
      }

      setFormData({ name: '', description: '' })
      setIsCreating(false)
      setIsEditing(false)
      setEditingId(null)
      load()
    } catch (error) {
      setError(`Error: ${error instanceof Error ? error.message : 'Failed to save location'}`)
    }
  }

  const handleEdit = (loc: Location) => {
    setFormData({ name: loc.name, description: loc.description || '' })
    setEditingId(loc.id)
    setIsEditing(true)
  }

  const handleDelete = async (id: number) => {
    try {
      await request(`/api/bevi-stoq/locations/${id}`, { method: 'DELETE' })
      load()
    } catch (error) {
      console.error('Delete error:', error)
    }
  }

  if (loading) return <Spinner label="Loading locations..." />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-3xl text-latte">Locations</h1>
        <Button onClick={() => setIsCreating(true)}>+ Add Location</Button>
      </div>

      {locations.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {locations.map((loc) => (
            <Card key={loc.id} className="flex flex-col">
              <div className="flex-1">
                <h3 className="font-semibold text-latte">{loc.name}</h3>
                {loc.description && <p className="mt-2 text-sm text-latte/60">{loc.description}</p>}
              </div>
              <div className="mt-4 flex gap-2 border-t border-caramel/15 pt-4">
                <Button variant="ghost" onClick={() => handleEdit(loc)} className="flex-1" icon={<Edit2 size={14} />}>
                  Edit
                </Button>
                <Button variant="danger" onClick={() => setDeleteConfirm(loc.id)} className="flex-1" icon={<Trash2 size={14} />}>
                  Deactivate
                </Button>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState
          title="No locations yet"
          hint="Create your first location (warehouse, storage, etc.)"
          action={<Button onClick={() => setIsCreating(true)}>+ Add Location</Button>}
        />
      )}

      <Modal
        open={isCreating || isEditing}
        onClose={() => {
          setIsCreating(false)
          setIsEditing(false)
          setFormData({ name: '', description: '' })
        }}
        title={isEditing ? 'Edit Location' : 'Add Location'}
      >
        <form
          onSubmit={(e: any) => {
            e.preventDefault()
            handleSave()
          }}
          className="space-y-4"
        >
          {error && (
            <div className="rounded-lg bg-red-500/20 px-3 py-2 text-sm text-red-300">
              {error}
            </div>
          )}
          <Field label="Location Name *">
            <Input
              value={formData.name}
              onChange={(e: any) => setFormData({ ...formData, name: e.target.value })}
              placeholder="e.g. Yercaud Warehouse"
              required
            />
          </Field>

          <Field label="Description">
            <Input
              value={formData.description}
              onChange={(e: any) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Optional description"
            />
          </Field>

          <div className="flex gap-3">
            <Button variant="ghost" onClick={() => setIsCreating(false)} type="button">
              Cancel
            </Button>
            <Button type="submit" className="flex-1">
              {isEditing ? 'Update' : 'Create'} Location
            </Button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        open={deleteConfirm !== null}
        title="Deactivate Location?"
        message="Location will be deactivated. History will be preserved."
        confirmLabel="Deactivate"
        onConfirm={() => {
          if (deleteConfirm) {
            handleDelete(deleteConfirm)
            setDeleteConfirm(null)
          }
        }}
        onCancel={() => setDeleteConfirm(null)}
      />
    </div>
  )
}
