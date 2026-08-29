import { Plus, Edit2, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api } from '../lib/api'
import { EmptyState, Spinner } from '../components/ui'
import { useToast } from '../lib/toast'
import { UnitSelect } from '../lib/units'

interface Product {
  id: number
  name: string
  category_id: number
  default_unit: string
  low_stock_threshold: number
  active: boolean
  created_at: string
}

interface Category {
  id: number
  name: string
}

interface Location {
  id: number
  name: string
}

export function BeviStoqProducts() {
  const toast = useToast()
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [locations, setLocations] = useState<Location[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({
    name: '',
    category_id: 0,
    default_unit: '',
    low_stock_threshold: 0,
  })
  const [initialStock, setInitialStock] = useState({
    quantity: '',
    unit: '',
    location_id: 0,
  })
  const [editingId, setEditingId] = useState<number | null>(null)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const [productsRes, categoriesRes, locationsRes] = await Promise.all([
        api.get<Product[]>('/api/bevi-stoq/products'),
        api.get<Category[]>('/api/bevi-stoq/categories'),
        api.get<Location[]>('/api/bevi-stoq/locations'),
      ])
      setProducts(productsRes)
      setCategories(categoriesRes)
      setLocations(locationsRes)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: any) => {
    e.preventDefault()
    try {
      let productId = editingId
      if (editingId) {
        await api.put(`/api/bevi-stoq/products/${editingId}`, formData)
      } else {
        const newProduct = await api.post<Product>('/api/bevi-stoq/products', formData)
        productId = newProduct.id
      }

      // Create initial inventory for new products if provided
      if (!editingId && productId && initialStock.quantity && initialStock.location_id) {
        await api.post('/api/bevi-stoq/stock-movements', {
          product_id: productId,
          to_location_id: initialStock.location_id,
          movement_type: 'opening_stock',
          quantity: parseFloat(initialStock.quantity),
          unit: initialStock.unit || formData.default_unit,
          reference_id: 0,
          notes: 'Opening stock',
        })
      }

      setFormData({ name: '', category_id: 0, default_unit: '', low_stock_threshold: 0 })
      setInitialStock({ quantity: '', unit: '', location_id: 0 })
      setEditingId(null)
      setShowForm(false)
      setError(null)
      toast.success(editingId ? 'Product updated successfully' : 'Product created successfully')
      await fetchData()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save product'
      setError(message)
      toast.error(message)
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
      category_id: product.category_id,
      default_unit: product.default_unit,
      low_stock_threshold: product.low_stock_threshold,
    })
    setEditingId(product.id)
    setShowForm(true)
  }

  const getCategoryName = (id: number) => categories.find((c) => c.id === id)?.name || 'Unknown'

  if (loading) return <Spinner label="Loading products…" />
  if (error) return <EmptyState emoji="⚠️" title="Error" hint={error} />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-latte">Products</h1>
          <p className="mt-1 text-sm text-latte/60">Manage inventory items with custom thresholds</p>
        </div>
        <button
          onClick={() => {
            setFormData({ name: '', category_id: 0, default_unit: '', low_stock_threshold: 0 })
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
                <label className="block text-sm font-medium text-latte">Product Name *</label>
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
                <label className="block text-sm font-medium text-latte">Category *</label>
                <select
                  value={formData.category_id}
                  onChange={(e) => setFormData({ ...formData, category_id: parseInt(e.target.value) })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                  required
                >
                  <option value={0}>Select category</option>
                  {categories.map((cat) => (
                    <option key={cat.id} value={cat.id}>
                      {cat.name}
                    </option>
                  ))}
                </select>
              </div>
              <UnitSelect
                value={formData.default_unit}
                onChange={(unit) => setFormData({ ...formData, default_unit: unit })}
                label="Unit"
                required={true}
              />
              <div>
                <label className="block text-sm font-medium text-latte">Low Stock Threshold</label>
                <input
                  type="number"
                  value={formData.low_stock_threshold}
                  onChange={(e) => {
                    const val = e.target.value;
                    const num = val === '' ? 0 : parseFloat(val);
                    setFormData({ ...formData, low_stock_threshold: isNaN(num) ? 0 : num })
                  }}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                  placeholder="0"
                  step="0.01"
                  min="0"
                  required
                />
              </div>
            </div>

            {!editingId && (
              <>
                <hr className="border-caramel/30" />
                <div>
                  <h3 className="mb-4 font-semibold text-latte">Initial Stock</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-latte">Quantity</label>
                      <input
                        type="number"
                        value={initialStock.quantity}
                        onChange={(e) => setInitialStock({ ...initialStock, quantity: e.target.value })}
                        className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte placeholder-latte/40 focus:outline-none focus:ring-2 focus:ring-gold/50"
                        placeholder="Enter quantity"
                        step="0.01"
                      />
                    </div>
                    <UnitSelect
                      value={initialStock.unit}
                      onChange={(unit) => setInitialStock({ ...initialStock, unit })}
                      label="Unit"
                      required={false}
                    />
                    <div className="col-span-2">
                      <label className="block text-sm font-medium text-latte">Location</label>
                      <select
                        value={initialStock.location_id}
                        onChange={(e) => setInitialStock({ ...initialStock, location_id: parseInt(e.target.value) })}
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
                </div>
              </>
            )}

            <div className="flex gap-3">
              <button
                type="submit"
                className="rounded bg-gold/20 px-4 py-2 text-sm font-medium text-gold hover:bg-gold/30"
              >
                {editingId ? 'Update' : 'Create'} Product
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

      {products.length === 0 ? (
        <EmptyState emoji="📦" title="No products" hint="Add your first product to start inventory management" />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-caramel/15">
          <table className="w-full">
            <thead>
              <tr className="border-b border-caramel/15 bg-espresso/60">
                <th className="px-4 py-3 text-left text-sm font-semibold text-latte">Product</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-latte">Category</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-latte">Unit</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-latte">Threshold</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-latte">Status</th>
                <th className="px-4 py-3 text-right text-sm font-semibold text-latte">Actions</th>
              </tr>
            </thead>
            <tbody>
              {products.map((product) => (
                <tr key={product.id} className="border-b border-caramel/15 hover:bg-espresso/40">
                  <td className="px-4 py-3 text-sm text-latte">{product.name}</td>
                  <td className="px-4 py-3 text-sm text-latte/70">{getCategoryName(product.category_id)}</td>
                  <td className="px-4 py-3 text-sm text-latte/70">{product.default_unit}</td>
                  <td className="px-4 py-3 text-sm text-latte/70">{product.low_stock_threshold}</td>
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
