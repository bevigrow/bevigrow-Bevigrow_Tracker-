import { Trash2, Edit2, Warehouse, Calendar } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { request } from '../../lib/api'
import { Button, Card, Input, Field, Modal, Select, Spinner, EmptyState, cx, ConfirmDialog } from '../../components/ui'

interface Product {
  id: number
  name: string
  category_id: number
  default_unit: string
  low_stock_alert_level: number
  active: boolean
  created_at: string
  created_by_user_id: number
}

interface Category {
  id: number
  name: string
}

interface LocationStock {
  location_id: number
  location_name: string
  physical_stock: number
  reserved_stock: number
  available_stock: number
}

interface RestockRecord {
  id: number
  quantity_restocked: number
  unit: string
  restock_date: string
  location_name: string
  supplier: string
  cost_per_unit: number
  total_cost: number
  reference_id?: string
  notes?: string
}

interface ProductDetail extends Product {
  total_physical_stock: number
  total_reserved_stock: number
  total_available_stock: number
  status: string
  location_stocks?: LocationStock[]
  restock_history?: RestockRecord[]
}

export function BeviStoqProducts() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [products, setProducts] = useState<ProductDetail[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [locations, setLocations] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [isCreating, setIsCreating] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)
  const [expandedProduct, setExpandedProduct] = useState<number | null>(null)
  const [expandedRestock, setExpandedRestock] = useState<number | null>(null)

  const [formData, setFormData] = useState({
    name: '',
    category_id: '',
    default_unit: 'kg',
    low_stock_alert_level: '0',
    initial_quantity: '',
    initial_location_id: '',
    initial_supplier: '',
    initial_cost: ''
  })

  const search = searchParams.get('search') || ''
  const categoryFilter = searchParams.get('category') || ''

  useEffect(() => {
    load()
  }, [search, categoryFilter])

  const load = async () => {
    try {
      setLoading(true)
      const [cats, locs] = await Promise.all([
        request<Category[]>('/api/bevi-stoq/categories?active_only=true&limit=1000'),
        request<any[]>('/api/bevi-stoq/locations?active_only=true&limit=1000')
      ])
      setCategories(cats)
      setLocations(locs)

      const params = new URLSearchParams()
      if (search) params.set('search', search)
      if (categoryFilter) params.set('category_id', categoryFilter)
      params.set('active_only', 'true')
      params.set('limit', '100')

      const prods = await request<ProductDetail[]>(`/api/bevi-stoq/products?${params}`)
      setProducts(prods)
    } catch (error) {
      console.error('Load error:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async () => {
    try {
      // Validate initial quantity fields if quantity is entered
      if (formData.initial_quantity) {
        if (!formData.initial_location_id) {
          alert('Location is required when adding initial quantity')
          return
        }
      }

      const payload = {
        name: formData.name,
        category_id: parseInt(formData.category_id),
        default_unit: formData.default_unit,
        low_stock_alert_level: parseFloat(formData.low_stock_alert_level)
      }

      let productId: number
      if (isEditing && editingId) {
        await request(`/api/bevi-stoq/products/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify(payload)
        })
        productId = editingId
      } else {
        const response = await request<any>('/api/bevi-stoq/products', {
          method: 'POST',
          body: JSON.stringify(payload)
        })
        productId = response.id
      }

      // Add initial stock if provided
      if (formData.initial_quantity && formData.initial_location_id && !isEditing) {
        await request('/api/bevi-stoq/stock/add', {
          method: 'POST',
          body: JSON.stringify({
            product_id: productId,
            location_id: parseInt(formData.initial_location_id),
            quantity: parseFloat(formData.initial_quantity),
            unit: formData.default_unit,
            cost_per_unit: formData.initial_cost ? parseFloat(formData.initial_cost) : null
          })
        })
      }

      setFormData({
        name: '',
        category_id: '',
        default_unit: 'kg',
        low_stock_alert_level: '0',
        initial_quantity: '',
        initial_location_id: '',
        initial_supplier: '',
        initial_cost: ''
      })
      setIsCreating(false)
      setIsEditing(false)
      setEditingId(null)
      load()
    } catch (error) {
      console.error('Error:', error)
    }
  }

  const handleEdit = (product: ProductDetail) => {
    setFormData({
      name: product.name,
      category_id: product.category_id.toString(),
      default_unit: product.default_unit,
      low_stock_alert_level: product.low_stock_alert_level.toString(),
      initial_quantity: '',
      initial_location_id: '',
      initial_supplier: '',
      initial_cost: ''
    })
    setEditingId(product.id)
    setIsEditing(true)
  }

  const handleDelete = async (id: number) => {
    try {
      await request(`/api/bevi-stoq/products/${id}`, { method: 'DELETE' })
      load()
    } catch (error) {
      console.error('Delete error:', error)
    }
  }

  if (loading) return <Spinner label="Loading products..." />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-3xl text-latte">Products</h1>
        <Button onClick={() => setIsCreating(true)}>+ Add Product</Button>
      </div>

      {/* Filters */}
      <Card>
        <div className="flex gap-4">
          <Input
            placeholder="Search products..."
            value={search}
            onChange={(e) => setSearchParams({ search: e.target.value })}
            className="flex-1"
          />
          <Select
            value={categoryFilter}
            onChange={(e) => setSearchParams({ category: e.target.value })}
            options={[
              { value: '', label: 'All Categories' },
              ...categories.map(c => ({ value: c.id.toString(), label: c.name }))
            ]}
          />
        </div>
      </Card>

      {/* Products List */}
      {products.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {products.map((product) => (
            <Card key={product.id} className="flex flex-col">
              <div className="flex-1">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-latte">{product.name}</h3>
                    <p className="text-xs text-latte/50">{product.default_unit}</p>
                  </div>
                  <span
                    className={cx(
                      'rounded-full px-2 py-1 text-xs font-medium',
                      product.status === 'OUT_OF_STOCK'
                        ? 'bg-red-500/20 text-red-300'
                        : product.status === 'LOW_STOCK'
                          ? 'bg-orange-500/20 text-orange-300'
                          : 'bg-green-500/20 text-green-300'
                    )}
                  >
                    {product.status}
                  </span>
                </div>

                <div className="mt-3 space-y-2 border-t border-caramel/15 pt-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-latte/60">Physical:</span>
                    <span className="text-latte">{product.total_physical_stock}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-latte/60">Reserved:</span>
                    <span className="text-latte">{product.total_reserved_stock}</span>
                  </div>
                  <div className="flex justify-between text-sm font-semibold">
                    <span className="text-latte/60">Available:</span>
                    <span className="text-gold">{product.total_available_stock}</span>
                  </div>
                </div>

                {/* Location Stock Breakdown */}
                {product.location_stocks && product.location_stocks.length > 0 && (
                  <div className="mt-3 border-t border-caramel/15 pt-3">
                    <button
                      onClick={() => setExpandedProduct(expandedProduct === product.id ? null : product.id)}
                      className="flex w-full items-center gap-2 text-xs font-medium text-latte/70 hover:text-latte"
                    >
                      <Warehouse size={14} />
                      Locations ({product.location_stocks.length})
                    </button>
                    {expandedProduct === product.id && (
                      <div className="mt-3 space-y-2">
                        {product.location_stocks.map((loc) => (
                          <div key={loc.location_id} className="rounded-lg bg-espresso/30 p-2.5">
                            <p className="text-xs font-semibold text-latte">{loc.location_name}</p>
                            <div className="mt-1.5 space-y-1">
                              <div className="flex justify-between text-xs">
                                <span className="text-latte/60">Available:</span>
                                <span className={loc.available_stock === 0 ? 'text-red-400' : 'text-gold'}>
                                  {loc.available_stock}
                                </span>
                              </div>
                              <div className="flex justify-between text-xs">
                                <span className="text-latte/60">Physical:</span>
                                <span className="text-latte/70">{loc.physical_stock}</span>
                              </div>
                              {loc.reserved_stock > 0 && (
                                <div className="flex justify-between text-xs">
                                  <span className="text-latte/60">Reserved:</span>
                                  <span className="text-orange-400">{loc.reserved_stock}</span>
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Restock Timeline */}
                {product.restock_history && product.restock_history.length > 0 && (
                  <div className="mt-3 border-t border-caramel/15 pt-3">
                    <button
                      onClick={() => setExpandedRestock(expandedRestock === product.id ? null : product.id)}
                      className="flex w-full items-center gap-2 text-xs font-medium text-latte/70 hover:text-latte"
                    >
                      <Calendar size={14} />
                      Restock Timeline ({product.restock_history.length})
                    </button>
                    {expandedRestock === product.id && (
                      <div className="mt-3 space-y-2">
                        {product.restock_history.map((restock, idx) => (
                          <div key={restock.id || idx} className="rounded-lg bg-espresso/30 p-2.5">
                            <div className="flex items-start justify-between gap-2">
                              <div className="flex-1">
                                <p className="text-xs font-semibold text-gold">
                                  {new Date(restock.restock_date).toLocaleDateString('en-IN', {
                                    day: '2-digit',
                                    month: 'short',
                                    year: 'numeric'
                                  })}
                                </p>
                                <p className="mt-1 text-xs text-latte/70">{restock.location_name}</p>
                              </div>
                              <div className="text-right">
                                <p className="text-xs font-semibold text-latte">
                                  +{restock.quantity_restocked} {restock.unit}
                                </p>
                              </div>
                            </div>
                            <div className="mt-2 border-t border-caramel/15 pt-2">
                              <div className="grid grid-cols-2 gap-2 text-xs">
                                {restock.supplier && (
                                  <div>
                                    <span className="text-latte/60">Supplier:</span>
                                    <p className="text-latte/80">{restock.supplier}</p>
                                  </div>
                                )}
                                <div>
                                  <span className="text-latte/60">Cost:</span>
                                  <p className="text-gold">₹{restock.total_cost.toLocaleString()}</p>
                                </div>
                              </div>
                            </div>
                            {restock.notes && (
                              <p className="mt-1.5 text-xs text-latte/50 italic">{restock.notes}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="mt-4 flex gap-2 border-t border-caramel/15 pt-4">
                <Button
                  variant="ghost"
                  onClick={() => handleEdit(product)}
                  className="flex-1"
                  icon={<Edit2 size={14} />}
                >
                  Edit
                </Button>
                <Button
                  variant="danger"
                  onClick={() => setDeleteConfirm(product.id)}
                  className="flex-1"
                  icon={<Trash2 size={14} />}
                >
                  Deactivate
                </Button>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState
          title="No products yet"
          hint="Create your first product to start managing inventory"
          action={<Button onClick={() => setIsCreating(true)}>+ Add Product</Button>}
        />
      )}

      {/* Create/Edit Modal */}
      <Modal
        open={isCreating || isEditing}
        onClose={() => {
          setIsCreating(false)
          setIsEditing(false)
          setEditingId(null)
          setFormData({
            name: '',
            category_id: '',
            default_unit: 'kg',
            low_stock_alert_level: '0',
            initial_quantity: '',
            initial_location_id: '',
            initial_supplier: '',
            initial_cost: ''
          })
        }}
        title={isEditing ? 'Edit Product' : 'Add Product'}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault()
            handleCreate()
          }}
          className="space-y-4"
        >
          <Field label="Product Name *">
            <Input
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="e.g. Pepper"
              required
            />
          </Field>

          <Field label="Category *">
            <Select
              value={formData.category_id}
              onChange={(e) => setFormData({ ...formData, category_id: e.target.value })}
              options={categories.map(c => ({ value: c.id.toString(), label: c.name }))}
              required
            />
          </Field>

          <Field label="Default Unit *">
            <Select
              value={formData.default_unit}
              onChange={(e) => setFormData({ ...formData, default_unit: e.target.value })}
              options={[
                { value: 'kg', label: 'kg' },
                { value: 'g', label: 'g' },
                { value: 'tonne', label: 'tonne' },
                { value: 'pcs', label: 'pcs' },
                { value: 'litre', label: 'litre' },
                { value: 'ml', label: 'ml' },
                { value: 'box', label: 'box' },
                { value: 'bag', label: 'bag' }
              ]}
            />
          </Field>

          <Field
            label="Low Stock Alert Level *"
            hint="Alert when available stock reaches or falls below this quantity"
          >
            <Input
              type="number"
              value={formData.low_stock_alert_level}
              onChange={(e) => setFormData({ ...formData, low_stock_alert_level: e.target.value })}
              placeholder="50"
              min="0"
              step="1"
              required
            />
          </Field>

          {/* Initial Quantity Section (Only when Creating) */}
          {!isEditing && (
            <>
              <div className="border-t border-caramel/15 pt-4 mt-4">
                <p className="text-sm font-semibold text-latte mb-3">📦 Initial Quantity</p>
              </div>

              <Field label="Quantity *">
                <Input
                  type="number"
                  placeholder="e.g. 100"
                  value={formData.initial_quantity}
                  onChange={(e) => setFormData({ ...formData, initial_quantity: e.target.value })}
                  required={formData.initial_quantity !== ''}
                />
              </Field>

              <Field label="Location *">
                <Select
                  value={formData.initial_location_id}
                  onChange={(e) => setFormData({ ...formData, initial_location_id: e.target.value })}
                  options={[
                    { value: '', label: 'Select location' },
                    ...locations.map(l => ({ value: l.id.toString(), label: l.name }))
                  ]}
                  required={formData.initial_quantity !== ''}
                />
              </Field>

              <Field label="Cost per Unit (₹)">
                <Input
                  type="number"
                  placeholder="0.00"
                  value={formData.initial_cost}
                  onChange={(e) => setFormData({ ...formData, initial_cost: e.target.value })}
                  step="0.01"
                />
              </Field>
            </>
          )}

          <div className="flex gap-3">
            <Button
              variant="ghost"
              onClick={() => {
                setIsCreating(false)
                setIsEditing(false)
                setFormData({
                  name: '',
                  category_id: '',
                  default_unit: 'kg',
                  low_stock_alert_level: '0',
                  initial_quantity: '',
                  initial_location_id: '',
                  initial_supplier: '',
                  initial_cost: ''
                })
              }}
              type="button"
            >
              Cancel
            </Button>
            <Button type="submit" className="flex-1">
              {isEditing ? 'Update' : 'Create'} Product
            </Button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={deleteConfirm !== null}
        title="Deactivate Product?"
        message="The product will be deactivated and won't appear in selections. Historical data will be preserved."
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
