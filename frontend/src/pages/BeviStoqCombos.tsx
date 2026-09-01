import { Plus, Edit2, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api } from '../lib/api'
import { EmptyState, Spinner } from '../components/ui'

interface ComboItem {
  id: number
  combo_id: number
  product_id: number
  quantity: number
  unit: string | null
  created_at: string
}

interface Combo {
  id: number
  name: string
  description: string | null
  active: boolean
  items: ComboItem[]
  created_at: string
}

interface Product {
  id: number
  name: string
  default_unit: string
}

export function BeviStoqCombos() {
  const [combos, setCombos] = useState<Combo[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    items: [{ product_id: 0, quantity: '', unit: '' }],
  })
  const [editingId, setEditingId] = useState<number | null>(null)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const [comboRes, prodRes] = await Promise.all([
        api.get<Combo[]>('/api/bevi-stoq/combos'),
        api.get<Product[]>('/api/bevi-stoq/products'),
      ])
      setCombos(comboRes || [])
      setProducts(prodRes || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load combos')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: any) => {
    e.preventDefault()
    try {
      const payload = {
        name: formData.name,
        description: formData.description,
        items: formData.items.map((item) => ({
          product_id: item.product_id,
          quantity: parseFloat(item.quantity),
          unit: item.unit || null,
        })),
      }
      if (editingId) {
        await api.put(`/api/bevi-stoq/combos/${editingId}`, payload)
      } else {
        await api.post('/api/bevi-stoq/combos', payload)
      }
      setFormData({ name: '', description: '', items: [{ product_id: 0, quantity: '', unit: '' }] })
      setEditingId(null)
      setShowForm(false)
      await fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save combo')
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this combo?')) return
    try {
      await api.delete(`/api/bevi-stoq/combos/${id}`)
      await fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete combo')
    }
  }

  const handleEdit = (combo: Combo) => {
    setFormData({
      name: combo.name,
      description: combo.description || '',
      items: combo.items.length > 0 ? combo.items.map((i) => ({ product_id: i.product_id, quantity: i.quantity.toString(), unit: i.unit || '' })) : [{ product_id: 0, quantity: '', unit: '' }],
    })
    setEditingId(combo.id)
    setShowForm(true)
  }

  const getProductName = (id: number) => products.find((p) => p.id === id)?.name || 'Unknown'
  const getProductUnit = (id: number) => products.find((p) => p.id === id)?.default_unit || ''

  if (loading) return <Spinner label="Loading combos…" />
  if (error) return <EmptyState emoji="⚠️" title="Error" hint={error} />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-latte">Product Combos</h1>
          <p className="mt-1 text-sm text-latte/60">Bundle products for quick ordering</p>
        </div>
        <button
          onClick={() => {
            setFormData({ name: '', description: '', items: [{ product_id: 0, quantity: '', unit: '' }] })
            setEditingId(null)
            setShowForm(!showForm)
          }}
          className="flex items-center gap-2 rounded-lg bg-gold/20 px-4 py-2 text-sm font-medium text-gold hover:bg-gold/30"
        >
          <Plus size={16} />
          New Combo
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="rounded-lg border border-caramel/15 bg-espresso/40 p-6">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-latte">Combo Name *</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte placeholder-latte/40 focus:outline-none focus:ring-2 focus:ring-gold/50"
                placeholder="e.g., Coffee Starter Pack"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-latte">Description</label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte placeholder-latte/40 focus:outline-none focus:ring-2 focus:ring-gold/50"
                placeholder="Combo description"
                rows={2}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-latte">Items *</label>
              <div className="mt-2 space-y-2">
                {formData.items.map((item, idx) => (
                  <div key={idx} className="flex gap-2">
                    <select
                      value={item.product_id}
                      onChange={(e) => {
                        const newItems = [...formData.items]
                        newItems[idx].product_id = parseInt(e.target.value)
                        setFormData({ ...formData, items: newItems })
                      }}
                      className="flex-1 rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                      required
                    >
                      <option value={0}>Select product</option>
                      {products.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                    <input
                      type="number"
                      value={item.quantity}
                      onChange={(e) => {
                        const newItems = [...formData.items]
                        newItems[idx].quantity = e.target.value
                        setFormData({ ...formData, items: newItems })
                      }}
                      className="w-20 rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                      placeholder="Qty"
                      step="0.01"
                      required
                    />
                    <select
                      value={item.unit}
                      onChange={(e) => {
                        const newItems = [...formData.items]
                        newItems[idx].unit = e.target.value
                        setFormData({ ...formData, items: newItems })
                      }}
                      className="w-20 rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                    >
                      <option value="">Unit</option>
                      <option value="g">g</option>
                      <option value="kg">kg</option>
                      <option value="tonne">tonne</option>
                      <option value="ml">ml</option>
                      <option value="litre">litre</option>
                      <option value="pcs">pcs</option>
                      <option value="box">box</option>
                      <option value="bag">bag</option>
                    </select>
                    <button
                      type="button"
                      onClick={() => {
                        const newItems = formData.items.filter((_, i) => i !== idx)
                        setFormData({ ...formData, items: newItems })
                      }}
                      className="rounded bg-red-500/20 px-2 text-red-400 hover:bg-red-500/30"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
              <button
                type="button"
                onClick={() => setFormData({ ...formData, items: [...formData.items, { product_id: 0, quantity: '', unit: '' }] })}
                className="mt-2 text-xs text-gold hover:text-gold/80"
              >
                + Add item
              </button>
            </div>

            <div className="flex gap-3">
              <button
                type="submit"
                className="rounded bg-gold/20 px-4 py-2 text-sm font-medium text-gold hover:bg-gold/30"
              >
                {editingId ? 'Update' : 'Create'} Combo
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

      {combos.length === 0 ? (
        <EmptyState emoji="📦" title="No combos" hint="Create your first product combo bundle" />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {combos.map((combo) => (
            <div key={combo.id} className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
              <div className="mb-3 flex items-start justify-between">
                <h3 className="font-semibold text-latte">{combo.name}</h3>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleEdit(combo)}
                    className="rounded p-1 hover:bg-caramel/20 text-latte/60 hover:text-gold"
                  >
                    <Edit2 size={16} />
                  </button>
                  <button
                    onClick={() => handleDelete(combo.id)}
                    className="rounded p-1 hover:bg-caramel/20 text-latte/60 hover:text-red-400"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
              {combo.description && <p className="mb-3 text-sm text-latte/60">{combo.description}</p>}
              <div className="space-y-1 border-t border-caramel/15 pt-3">
                {combo.items.map((item) => (
                  <div key={item.id} className="flex justify-between text-xs">
                    <span className="text-latte/70">{getProductName(item.product_id)}</span>
                    <span className="text-latte/50">{item.quantity} {item.unit || getProductUnit(item.product_id)}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
