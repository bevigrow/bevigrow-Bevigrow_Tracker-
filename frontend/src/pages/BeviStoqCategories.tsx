import { Plus, Edit2, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api } from '../lib/api'
import { EmptyState, Spinner } from '../components/ui'

interface Category {
  id: number
  name: string
  description: string | null
  active: boolean
  created_at: string
}

export function BeviStoqCategories() {
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({ name: '', description: '' })
  const [editingId, setEditingId] = useState<number | null>(null)

  useEffect(() => {
    fetchCategories()
  }, [])

  const fetchCategories = async () => {
    try {
      const response = await api.get<Category[]>('/api/bevi-stoq/categories')
      setCategories(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load categories')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: any) => {
    e.preventDefault()
    try {
      if (editingId) {
        await api.put(`/api/bevi-stoq/categories/${editingId}`, formData)
      } else {
        await api.post('/api/bevi-stoq/categories', formData)
      }
      setFormData({ name: '', description: '' })
      setEditingId(null)
      setShowForm(false)
      await fetchCategories()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save category')
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this category?')) return
    try {
      await api.delete(`/api/bevi-stoq/categories/${id}`)
      await fetchCategories()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete category')
    }
  }

  const handleEdit = (category: Category) => {
    setFormData({ name: category.name, description: category.description || '' })
    setEditingId(category.id)
    setShowForm(true)
  }

  if (loading) return <Spinner label="Loading categories…" />
  if (error) return <EmptyState emoji="⚠️" title="Error" hint={error} />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-latte">Product Categories</h1>
          <p className="mt-1 text-sm text-latte/60">Organize your inventory</p>
        </div>
        <button
          onClick={() => {
            setFormData({ name: '', description: '' })
            setEditingId(null)
            setShowForm(!showForm)
          }}
          className="flex items-center gap-2 rounded-lg bg-gold/20 px-4 py-2 text-sm font-medium text-gold hover:bg-gold/30"
        >
          <Plus size={16} />
          Add Category
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="rounded-lg border border-caramel/15 bg-espresso/40 p-6">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-latte">Category Name</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte placeholder-latte/40 focus:outline-none focus:ring-2 focus:ring-gold/50"
                placeholder="e.g., Beverages, Coffee Beans"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-latte">Description</label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte placeholder-latte/40 focus:outline-none focus:ring-2 focus:ring-gold/50"
                placeholder="Optional description"
                rows={3}
              />
            </div>
            <div className="flex gap-3">
              <button
                type="submit"
                className="rounded bg-gold/20 px-4 py-2 text-sm font-medium text-gold hover:bg-gold/30"
              >
                {editingId ? 'Update' : 'Create'} Category
              </button>
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="rounded border border-caramel/30 px-4 py-2 text-sm font-medium text-latte/60 hover:bg-caramel/10"
              >
                Cancel
              </button>
            </div>
          </div>
        </form>
      )}

      {categories.length === 0 ? (
        <EmptyState emoji="🏷️" title="No categories" hint="Create your first category to organize products" />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {categories.map((category) => (
            <div key={category.id} className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
              <div className="mb-3 flex items-start justify-between">
                <h3 className="font-semibold text-latte">{category.name}</h3>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleEdit(category)}
                    className="rounded p-1 hover:bg-caramel/20 text-latte/60 hover:text-gold"
                  >
                    <Edit2 size={16} />
                  </button>
                  <button
                    onClick={() => handleDelete(category.id)}
                    className="rounded p-1 hover:bg-caramel/20 text-latte/60 hover:text-red-400"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
              {category.description && <p className="text-sm text-latte/60">{category.description}</p>}
              <p className="mt-2 text-xs text-latte/40">
                {category.active ? '✓ Active' : '✗ Inactive'}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
