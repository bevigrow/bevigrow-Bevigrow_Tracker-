import { Trash2, Edit2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { request } from '../../lib/api'
import { Button, Card, Input, Field, Modal, Spinner, EmptyState, ConfirmDialog } from '../../components/ui'

interface Category {
  id: number
  name: string
  description?: string
  active: boolean
  created_at: string
}

export function BeviStoqCategories() {
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(true)
  const [isCreating, setIsCreating] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)

  const [formData, setFormData] = useState({ name: '', description: '' })

  useEffect(() => {
    load()
  }, [])

  const load = async () => {
    try {
      setLoading(true)
      const data = await request<Category[]>('/api/bevi-stoq/categories?active_only=true&limit=1000')
      setCategories(data)
    } catch (error) {
      console.error('Load error:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    try {
      const payload = { name: formData.name, description: formData.description }

      if (isEditing && editingId) {
        await request(`/api/bevi-stoq/categories/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify(payload)
        })
      } else {
        await request('/api/bevi-stoq/categories', {
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
      console.error('Error:', error)
    }
  }

  const handleEdit = (cat: Category) => {
    setFormData({ name: cat.name, description: cat.description || '' })
    setEditingId(cat.id)
    setIsEditing(true)
  }

  const handleDelete = async (id: number) => {
    try {
      await request(`/api/bevi-stoq/categories/${id}`, { method: 'DELETE' })
      load()
    } catch (error) {
      console.error('Delete error:', error)
    }
  }

  if (loading) return <Spinner label="Loading categories..." />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-3xl text-latte">Categories</h1>
        <Button onClick={() => setIsCreating(true)}>+ Add Category</Button>
      </div>

      {categories.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {categories.map((cat) => (
            <Card key={cat.id} className="flex flex-col">
              <div className="flex-1">
                <h3 className="font-semibold text-latte">{cat.name}</h3>
                {cat.description && <p className="mt-2 text-sm text-latte/60">{cat.description}</p>}
              </div>
              <div className="mt-4 flex gap-2 border-t border-caramel/15 pt-4">
                <Button variant="ghost" onClick={() => handleEdit(cat)} className="flex-1" icon={<Edit2 size={14} />}>
                  Edit
                </Button>
                <Button variant="danger" onClick={() => setDeleteConfirm(cat.id)} className="flex-1" icon={<Trash2 size={14} />}>
                  Deactivate
                </Button>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState
          title="No categories yet"
          hint="Create your first category"
          action={<Button onClick={() => setIsCreating(true)}>+ Add Category</Button>}
        />
      )}

      <Modal
        open={isCreating || isEditing}
        onClose={() => {
          setIsCreating(false)
          setIsEditing(false)
          setFormData({ name: '', description: '' })
        }}
        title={isEditing ? 'Edit Category' : 'Add Category'}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault()
            handleSave()
          }}
          className="space-y-4"
        >
          <Field label="Category Name *">
            <Input
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="e.g. Spices"
              required
            />
          </Field>

          <Field label="Description">
            <Input
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Optional description"
            />
          </Field>

          <div className="flex gap-3">
            <Button variant="ghost" onClick={() => setIsCreating(false)} type="button">
              Cancel
            </Button>
            <Button type="submit" className="flex-1">
              {isEditing ? 'Update' : 'Create'} Category
            </Button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        open={deleteConfirm !== null}
        title="Deactivate Category?"
        message="Category will be deactivated. Products will keep their history."
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
