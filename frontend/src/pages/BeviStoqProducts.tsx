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
  low_stock_threshold: number | null
  low_stock_threshold_unit: string | null
  packaging_status: string
  notes: string | null
  active: boolean
  created_at: string
}

interface InventoryItem {
  id: number
  product_id: number
  location_id: number
  physical_stock: number
  reserved_stock: number
  available_stock?: number
}

interface Location {
  id: number
  name: string
}

interface Category {
  id: number
  name: string
}

const UNITS = ['g', 'kg', 'tonne', 'ml', 'litre', 'pcs', 'box', 'bag']

interface ProductWithStock extends Product {
  total_stock: number
}

export function BeviStoqProducts() {
  const toast = useToast()
  const [products, setProducts] = useState<ProductWithStock[]>([])
  const [locations, setLocations] = useState<Location[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [formData, setFormData] = useState({
    name: '',
    default_unit: '',
    stock_quantity: '',
    location_id: 0,
    category_id: 0,
    packaging_status: 'unpacked',
    low_stock_threshold: '',
    low_stock_threshold_unit: '',
    notes: '',
    current_quantity: '', // For edit mode - existing stock
  })
  const [editingId, setEditingId] = useState<number | null>(null)
  const [inventory, setInventory] = useState<any[]>([])
  const [filterPackagingStatus, setFilterPackagingStatus] = useState<string | null>(null)
  const [filterCategoryId, setFilterCategoryId] = useState<number | null>(null)

  useEffect(() => {
    fetchData()
  }, [filterPackagingStatus, filterCategoryId])

  const fetchData = async () => {
    try {
      console.log('[fetchData] Starting data fetch...')
      const params = new URLSearchParams()
      if (filterPackagingStatus) params.append('packaging_status', filterPackagingStatus)
      if (filterCategoryId) params.append('category_id', filterCategoryId.toString())
      const productsUrl = `/api/bevi-stoq/products${params.size > 0 ? '?' + params.toString() : ''}`

      const [productsRes, locationsRes, categoriesRes, inventoryRes] = await Promise.all([
        api.get<Product[]>(productsUrl),
        api.get<Location[]>('/api/bevi-stoq/locations'),
        api.get<Category[]>('/api/bevi-stoq/categories'),
        api.get<InventoryItem[]>('/api/bevi-stoq/inventory'),
      ])

      console.log('[fetchData] Products fetched:', productsRes)
      console.log('[fetchData] Inventory fetched:', inventoryRes)

      // Calculate total stock per product
      const stockByProduct = new Map<number, number>()
      inventoryRes.forEach((inv) => {
        const available = inv.physical_stock - inv.reserved_stock
        const current = stockByProduct.get(inv.product_id) || 0
        stockByProduct.set(inv.product_id, current + available)
      })

      // Add total_stock to each product
      const productsWithStock: ProductWithStock[] = productsRes.map((prod) => ({
        ...prod,
        total_stock: stockByProduct.get(prod.id) || 0,
      }))

      console.log('[fetchData] Products with stock:', productsWithStock)
      setProducts(productsWithStock)
      setLocations(locationsRes)
      setCategories(categoriesRes)
      setInventory(inventoryRes)
      console.log('[fetchData] State updated successfully')
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : 'Failed to load data'
      console.error('[fetchData] Error:', errMsg, err)
      setError(errMsg)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: any) => {
    e.preventDefault()
    console.log('handleSubmit called, editingId:', editingId, 'formData:', formData, 'submitting:', submitting)
    if (submitting) {
      console.log('Already submitting, returning')
      return
    }
    setSubmitting(true)
    setError(null)

    // Validation for CREATE
    if (!editingId) {
      if (!formData.name.trim()) {
        setError('Product Name is required')
        setSubmitting(false)
        return
      }
      if (!formData.default_unit) {
        setError('Unit is required')
        setSubmitting(false)
        return
      }
      if (!formData.stock_quantity || parseFloat(formData.stock_quantity) <= 0) {
        setError('Stock Quantity is required and must be a positive number')
        setSubmitting(false)
        return
      }
      if (formData.location_id === 0) {
        setError('Location is required')
        setSubmitting(false)
        return
      }
      if (formData.category_id === 0) {
        setError('Category is required')
        setSubmitting(false)
        return
      }
    }

    // Validation for UPDATE
    if (editingId) {
      console.log('Validating UPDATE: name=', formData.name, 'unit=', formData.default_unit)
      if (!formData.name.trim()) {
        setError('Product Name is required')
        setSubmitting(false)
        return
      }
      if (!formData.default_unit) {
        setError('Unit is required')
        setSubmitting(false)
        return
      }
    }

    try {
      const payload: any = {
        name: formData.name.trim(),
        category_id: formData.category_id || null,
        default_unit: formData.default_unit,
        packaging_status: formData.packaging_status || 'unpacked',
        low_stock_threshold: formData.low_stock_threshold ? parseFloat(formData.low_stock_threshold) : null,
        low_stock_threshold_unit: formData.low_stock_threshold_unit || null,
        alert_quantity: null,
        notes: formData.notes || null,
      }

      // For updates (edit mode), include quantity
      if (editingId && formData.current_quantity) {
        const qty = parseFloat(formData.current_quantity)
        if (!isNaN(qty)) {
          payload.quantity = qty
        }
      }

      console.log('Payload:', payload)
      let productId = editingId
      if (editingId) {
        console.log(`[UPDATE] Updating product id=${editingId} with payload:`, payload)
        try {
          const apiResponse = await api.put<Product>(`/api/bevi-stoq/products/${editingId}`, payload)
          console.log('[UPDATE] API Response:', apiResponse)

          // Don't trust the API response - fetch fresh data from database to verify persistence
          console.log('[UPDATE] Fetching fresh data to verify database persistence...')
          await fetchData()
          console.log('[UPDATE] Fresh data fetched - database update verified')

          // Verify the update actually persisted by checking the fresh data
          const updatedProductInList = products.find(p => p.id === editingId)
          if (updatedProductInList && updatedProductInList.name === payload.name) {
            console.log('[UPDATE] ✓ Database persistence confirmed - values match')
            setFormData({ name: '', default_unit: '', stock_quantity: '', location_id: 0, category_id: 0, packaging_status: 'unpacked', low_stock_threshold: '', notes: '', current_quantity: '' })
            setEditingId(null)
            setShowForm(false)
            toast.success('Product updated successfully')
          } else {
            console.error('[UPDATE] ✗ Database persistence FAILED - fresh data does not match sent values')
            console.log('Sent:', payload.name, 'Got:', updatedProductInList?.name)
            setError('Update failed: Database did not persist changes. Please try again.')
            toast.error('Update failed: Changes were not saved to database')
          }
        } catch (apiError) {
          console.error('[UPDATE] API call failed:', apiError)
          const errorMsg = apiError instanceof Error ? apiError.message : 'API request failed'
          setError(errorMsg)
          toast.error(`Update failed: ${errorMsg}`)
          throw apiError
        }
      } else {
        const newProduct = await api.post<Product>('/api/bevi-stoq/products', payload)
        productId = newProduct.id
        console.log(`Product created: id=${productId}, name=${newProduct.name}`)

        // Create stock movement if quantity and location provided
        if (productId && formData.stock_quantity && formData.location_id > 0) {
          const qty = parseFloat(formData.stock_quantity)
          if (isNaN(qty) || qty <= 0) {
            throw new Error('Stock quantity must be a valid positive number')
          }
          console.log(`Creating stock movement: product_id=${productId}, qty=${qty}, location=${formData.location_id}`)
          await api.post('/api/bevi-stoq/stock-movements', {
            product_id: productId,
            to_location_id: formData.location_id,
            movement_type: 'opening_stock',
            quantity: qty,
            unit: formData.default_unit,
            reference_id: null,
            notes: formData.notes || 'Initial stock',
          })
          console.log('Stock movement created successfully')
        } else if (!formData.stock_quantity || formData.location_id === 0) {
          console.log('Stock quantity or location not provided, skipping stock movement')
        }

        setFormData({ name: '', default_unit: '', stock_quantity: '', location_id: 0, category_id: 0, packaging_status: 'unpacked', low_stock_threshold: '', notes: '', current_quantity: '' })
        setEditingId(null)
        setShowForm(false)
        toast.success('Product created successfully with stock')
      }
      console.log('About to fetch data...')
      await fetchData()
      console.log('Data fetched successfully')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save product'
      console.error('[ERROR] Form submission error:', message, err)
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
    // Calculate current total stock from inventory
    const totalStock = inventory
      .filter((inv) => inv.product_id === product.id)
      .reduce((sum, inv) => sum + (inv.physical_stock - inv.reserved_stock), 0)

    setFormData({
      name: product.name,
      default_unit: product.default_unit,
      stock_quantity: '',
      location_id: 0,
      category_id: product.category_id || 0,
      packaging_status: product.packaging_status || 'unpacked',
      low_stock_threshold: product.low_stock_threshold ? product.low_stock_threshold.toString() : '',
      low_stock_threshold_unit: product.low_stock_threshold_unit || '',
      notes: product.notes || '',
      current_quantity: totalStock.toString(),
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
            setFormData({ name: '', default_unit: '', stock_quantity: '', location_id: 0, category_id: 0, packaging_status: 'unpacked', low_stock_threshold: '', low_stock_threshold_unit: '', notes: '', current_quantity: '' })
            setEditingId(null)
            setShowForm(!showForm)
          }}
          className="flex items-center gap-2 rounded-lg bg-gold/20 px-4 py-2 text-sm font-medium text-gold hover:bg-gold/30"
        >
          <Plus size={16} />
          Add Product
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 rounded-lg border border-caramel/15 bg-espresso/40 p-4">
        <div>
          <label className="block text-xs font-medium text-latte/60 mb-1">Packaging Status</label>
          <select
            value={filterPackagingStatus || ''}
            onChange={(e) => setFilterPackagingStatus(e.target.value || null)}
            className="rounded bg-bean/50 px-3 py-2 text-sm text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
          >
            <option value="">All Products</option>
            <option value="packed">Packed</option>
            <option value="unpacked">Unpacked</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-latte/60 mb-1">Category</label>
          <select
            value={filterCategoryId || ''}
            onChange={(e) => setFilterCategoryId(e.target.value ? parseInt(e.target.value) : null)}
            className="rounded bg-bean/50 px-3 py-2 text-sm text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
          >
            <option value="">All Categories</option>
            {categories.map((cat) => (
              <option key={cat.id} value={cat.id}>
                {cat.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="rounded-lg border border-caramel/15 bg-espresso/40 p-6">
          <div className="mb-4 pb-4 border-b border-caramel/15">
            <h2 className="text-lg font-semibold text-latte">
              {editingId ? 'Edit Product Details' : 'Add New Product'}
            </h2>
            <p className="text-xs text-latte/60 mt-1">
              {editingId
                ? 'Update product name, unit, category, and notes. Use Stock Movements to adjust inventory.'
                : 'Create a new product with initial stock level'}
            </p>
          </div>
          {error && (
            <div className="mb-4 rounded-lg bg-red-500/20 p-4 text-red-400">
              <p className="text-sm font-medium">Error: {error}</p>
            </div>
          )}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-latte">
                Product Name <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte placeholder-latte/40 focus:outline-none focus:ring-2 focus:ring-gold/50"
                placeholder="e.g., Arabica Beans"
                required
              />
            </div>

            {editingId && (
              <div>
                <label className="block text-sm font-medium text-latte">
                  Quantity <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  inputMode="decimal"
                  value={formData.current_quantity}
                  onChange={(e) => setFormData({ ...formData, current_quantity: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte placeholder-latte/40 focus:outline-none focus:ring-2 focus:ring-gold/50"
                  placeholder="e.g., 250"
                  required
                />
              </div>
            )}

            {!editingId && (
              <div>
                <label className="block text-sm font-medium text-latte">
                  Stock Quantity <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={formData.stock_quantity}
                  onChange={(e) => setFormData({ ...formData, stock_quantity: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte placeholder-latte/40 focus:outline-none focus:ring-2 focus:ring-gold/50"
                  placeholder="e.g., 1000"
                  required
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-latte">
                Unit <span className="text-red-400">*</span>
              </label>
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

            {!editingId && (
              <div>
                <label className="block text-sm font-medium text-latte">
                  Location <span className="text-red-400">*</span>
                </label>
                <select
                  value={formData.location_id || ''}
                  onChange={(e) => setFormData({ ...formData, location_id: e.target.value ? parseInt(e.target.value) : 0 })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                  required
                >
                  <option value="">Select location</option>
                  {locations.map((loc) => (
                    <option key={loc.id} value={loc.id}>
                      {loc.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-latte">
                Category {editingId ? <span className="text-latte/60">(optional)</span> : <span className="text-red-400">*</span>}
              </label>
              <select
                value={formData.category_id || ''}
                onChange={(e) => setFormData({ ...formData, category_id: e.target.value ? parseInt(e.target.value) : 0 })}
                className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                required={!editingId}
              >
                <option value="">Select category</option>
                {categories.map((cat) => (
                  <option key={cat.id} value={cat.id}>
                    {cat.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-latte">
                Packaging Status <span className="text-latte/60">(optional)</span>
              </label>
              <select
                value={formData.packaging_status}
                onChange={(e) => setFormData({ ...formData, packaging_status: e.target.value })}
                className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
              >
                <option value="unpacked">Unpacked</option>
                <option value="packed">Packed</option>
              </select>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="col-span-2">
                <label className="block text-sm font-medium text-latte">
                  Low Stock Threshold <span className="text-latte/60">(optional)</span>
                </label>
                <input
                  type="text"
                  inputMode="decimal"
                  value={formData.low_stock_threshold}
                  onChange={(e) => setFormData({ ...formData, low_stock_threshold: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte placeholder-latte/40 focus:outline-none focus:ring-2 focus:ring-gold/50"
                  placeholder="e.g., 50"
                  step="0.01"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-latte">Unit</label>
                <select
                  value={formData.low_stock_threshold_unit || formData.default_unit}
                  onChange={(e) => setFormData({ ...formData, low_stock_threshold_unit: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                >
                  <option value="">{formData.default_unit || 'Unit'}</option>
                  {UNITS.map((unit) => (
                    <option key={unit} value={unit}>
                      {unit}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-latte">
                Note <span className="text-latte/60">(optional)</span>
              </label>
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
                <th className="px-4 py-3 text-center text-sm font-semibold text-latte">Quantity</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-latte">Status</th>
                <th className="px-4 py-3 text-right text-sm font-semibold text-latte">Actions</th>
              </tr>
            </thead>
            <tbody>
              {products.map((product) => (
                <tr key={product.id} className="border-b border-caramel/15 hover:bg-espresso/40">
                  <td className="px-4 py-3 text-sm text-latte">{product.name}</td>
                  <td className="px-4 py-3 text-sm text-latte/70">{product.default_unit}</td>
                  <td className="px-4 py-3 text-center text-sm">
                    <span className={`font-semibold ${product.total_stock > 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {product.total_stock.toFixed(2)}
                    </span>
                  </td>
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
