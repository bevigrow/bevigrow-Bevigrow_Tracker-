import { Plus, Edit2, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api } from '../lib/api'
import { EmptyState, Spinner } from '../components/ui'
import { useToast } from '../lib/toast'

interface Product {
  id: number
  name: string
  category_id: number | null
  default_unit: string
  alert_quantity: number | null
  active: boolean
  created_at: string
}

interface Location {
  id: number
  name: string
}

const UNITS = ['g', 'kg', 'pcs']

export function BeviStoqProducts() {
  const toast = useToast()
  const [products, setProducts] = useState<Product[]>([])
  const [locations, setLocations] = useState<Location[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [formData, setFormData] = useState({
    name: '',
    default_unit: '',
    stock_quantity: '',
    location_id: 0,
    notes: '',
  })
  const [editingId, setEditingId] = useState<number | null>(null)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const [productsRes, locationsRes] = await Promise.all([
        api.get<Product[]>('/api/bevi-stoq/products'),
        api.get<Location[]>('/api/bevi-stoq/locations'),
      ])
      setProducts(productsRes)
      setLocations(locationsRes)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: any) => {
    e.preventDefault()
    if (submitting) return // Prevent double-submit
    setSubmitting(true)
    try {
      const payload = {
        name: formData.name.trim(),
        category_id: null,
        default_unit: formData.default_unit,
        alert_quantity: null,
      }

      let productId = editingId
      if (editingId) {
        await api.put(`/api/bevi-stoq/products/${editingId}`, payload)
      } else {
        const newProduct = await api.post<Product>('/api/bevi-stoq/products', payload)
        productId = newProduct.id

        // Create stock movement if quantity and location provided
        if (productId && formData.stock_quantity && formData.location_id) {
          await api.post('/api/bevi-stoq/stock-movements', {
            product_id: productId,
            to_location_id: formData.location_id,
            movement_type: 'opening_stock',
            quantity: parseFloat(formData.stock_quantity),
            unit: formData.default_unit,
            reference_id: null,
            notes: formData.notes || 'Initial stock',
          })
        }
      }

      setFormData({ name: '', default_unit: '', stock_quantity: '', location_id: 0, notes: '' })
      setEditingId(null)
      setShowForm(false)
      setError(null)
      toast.success(editingId ? 'Product updated successfully' : 'Product created successfully')
      await fetchData()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save product'
      setError(message)
      toast.error(message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this product?')) return
    try {
      await api.delete(`/api/bevi-stoq/products/${id}`)
      await fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete product')
    }
  }

  const handleEdit = (product: Product) => {
    setFormData({
      name: product.name,
      default_unit: product.default_unit,
      stock_quantity: '',
      location_id: 0,
      notes: '',
    })
    setEditingId(product.id)
    setShowForm(true)
  }

  if (loading) return <Spinner label="Loading products…" />
  if (error) return <EmptyState emoji="⚠️" title="Error" hint={error} />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-latte">Products</h1>
          <p className="mt-1 text-sm text-latte/60">Manage inventory items</p>
        </div>
        <button
          onClick={() => {
            setFormData({ name: '', default_unit: '', stock_quantity: '', location_id: 0, notes: '' })
            setEditingId(null)
            setShowForm(!showForm)
          }}
          className="flex items-center gap-2 rounded-lg bg-gold/20 px-4 py-2 text-sm font-medium text-gold hover:bg-gold/30"
        >
          <Plus size={16} />
          Add Product
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="rounded-lg border border-caramel/15 bg-espresso/40 p-6">
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-latte">Product Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte placeholder-latte/40 focus:outline-none focus:ring-2 focus:ring-gold/50"
                  placeholder="e.g., Arabica Beans"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-latte">Stock Quantity</label>
                <input
                  type="text"
                  value={formData.stock_quantity}
                  onChange={(e) => setFormData({ ...formData, stock_quantity: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte placeholder-latte/40 focus:outline-none focus:ring-2 focus:ring-gold/50"
                  placeholder="e.g., 1000"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-latte">Unit</label>
                <select
                  value={formData.default_unit}
                  onChange={(e) => setFormData({ ...formData, default_unit: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                  required
                >
                  <option value="">Select unit</option>
                  {UNITS.map((unit) => (
                    <option key={unit} value={unit}>
                      {unit}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-latte">Location</label>
                <select
                  value={formData.location_id}
                  onChange={(e) => setFormData({ ...formData, location_id: parseInt(e.target.value) })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                >
                  <option value={0}>Select location</option>
                  {locations.map((loc) => (
                    <option key={loc.id} value={loc.id}>
                      {loc.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-latte">Note (optional)</label>
              <input
                type="text"
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte placeholder-latte/40 focus:outline-none focus:ring-2 focus:ring-gold/50"
                placeholder="Add notes about this product"
              />
            </div>

            <div className="flex gap-3">
              <button
                type="submit"
                disabled={submitting}
                className="rounded bg-gold/20 px-4 py-2 text-sm font-medium text-gold hover:bg-gold/30 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? 'Saving...' : (editingId ? 'Update' : 'Create')} Product
              </button>
              <button
                type="button"
                onClick={() => setShowForm(false)}
                disabled={submitting}
                className="rounded border border-caramel/30 px-4 py-2 text-sm font-medium text-latte/60 hover:bg-caramel/10 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Cancel
              </button>
            </div>
          </div>
        </form>
      )}

      {products.length === 0 ? (
        <EmptyState emoji="📦" title="No products" hint="Add your first product to start inventory management" />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-caramel/15">
          <table className="w-full">
            <thead>
              <tr className="border-b border-caramel/15 bg-espresso/60">
                <th className="px-4 py-3 text-left text-sm font-semibold text-latte">Product</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-latte">Unit</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-latte">Status</th>
                <th className="px-4 py-3 text-right text-sm font-semibold text-latte">Actions</th>
              </tr>
            </thead>
            <tbody>
              {products.map((product) => (
                <tr key={product.id} className="border-b border-caramel/15 hover:bg-espresso/40">
                  <td className="px-4 py-3 text-sm text-latte">{product.name}</td>
                  <td className="px-4 py-3 text-sm text-latte/70">{product.default_unit}</td>
                  <td className="px-4 py-3 text-sm">
                    <span className="text-xs text-latte/50">{product.active ? '✓ Active' : '✗ Inactive'}</span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => handleEdit(product)}
                        className="rounded p-1 hover:bg-caramel/20 text-latte/60 hover:text-gold"
                      >
                        <Edit2 size={16} />
                      </button>
                      <button
                        onClick={() => handleDelete(product.id)}
                        className="rounded p-1 hover:bg-caramel/20 text-latte/60 hover:text-red-400"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
