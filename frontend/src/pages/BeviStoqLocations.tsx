import { Plus, Edit2, Trash2, MapPin } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api } from '../lib/api'
import { EmptyState, Spinner } from '../components/ui'

interface Location {
  id: number
  name: string
  description: string | null
  active: boolean
  created_at: string
}

export function BeviStoqLocations() {
  const [locations, setLocations] = useState<Location[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({ name: '', description: '' })
  const [editingId, setEditingId] = useState<number | null>(null)

  useEffect(() => {
    fetchLocations()
  }, [])

  const fetchLocations = async () => {
    try {
      const response = await api.get<Location[]>('/api/bevi-stoq/locations')
      setLocations(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load locations')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: any) => {
    e.preventDefault()
    try {
      if (editingId) {
        await api.put(`/api/bevi-stoq/locations/${editingId}`, formData)
      } else {
        await api.post('/api/bevi-stoq/locations', formData)
      }
      setFormData({ name: '', description: '' })
      setEditingId(null)
      setShowForm(false)
      await fetchLocations()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save location')
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this location?')) return
    try {
      await api.delete(`/api/bevi-stoq/locations/${id}`)
      await fetchLocations()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete location')
    }
  }

  const handleEdit = (location: Location) => {
    setFormData({ name: location.name, description: location.description || '' })
    setEditingId(location.id)
    setShowForm(true)
  }

  if (loading) return <Spinner label="Loading locations…" />
  if (error) return <EmptyState emoji="⚠️" title="Error" hint={error} />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-latte">Storage Locations</h1>
          <p className="mt-1 text-sm text-latte/60">Warehouses and storage facilities</p>
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
          Add Location
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="rounded-lg border border-caramel/15 bg-espresso/40 p-6">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-latte">Location Name</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte placeholder-latte/40 focus:outline-none focus:ring-2 focus:ring-gold/50"
                placeholder="e.g., Main Warehouse, Cold Storage"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-latte">Description</label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte placeholder-latte/40 focus:outline-none focus:ring-2 focus:ring-gold/50"
                placeholder="Address, capacity, or notes"
                rows={3}
              />
            </div>
            <div className="flex gap-3">
              <button
                type="submit"
                className="rounded bg-gold/20 px-4 py-2 text-sm font-medium text-gold hover:bg-gold/30"
              >
                {editingId ? 'Update' : 'Create'} Location
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

      {locations.length === 0 ? (
        <EmptyState emoji="📍" title="No locations" hint="Add your first storage location" />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {locations.map((location) => (
            <div key={location.id} className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
              <div className="mb-3 flex items-start justify-between">
                <div className="flex items-start gap-3">
                  <MapPin size={18} className="mt-1 text-gold/60" />
                  <h3 className="font-semibold text-latte">{location.name}</h3>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleEdit(location)}
                    className="rounded p-1 hover:bg-caramel/20 text-latte/60 hover:text-gold"
                  >
                    <Edit2 size={16} />
                  </button>
                  <button
                    onClick={() => handleDelete(location.id)}
                    className="rounded p-1 hover:bg-caramel/20 text-latte/60 hover:text-red-400"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
              {location.description && <p className="text-sm text-latte/60">{location.description}</p>}
              <p className="mt-2 text-xs text-latte/40">
                {location.active ? '✓ Active' : '✗ Inactive'}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
