import { Trash2, Edit2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { request } from '../../lib/api'
import { Button, Card, Input, Field, Modal, Select, Spinner, EmptyState, ConfirmDialog } from '../../components/ui'

interface RestockRecord {
  id: number
  product_id: number
  product_name: string
  category_name: string
  location_id: number
  location_name: string
  quantity_restocked: number
  unit: string
  restock_date: string
  supplier: string
  cost_per_unit: number
  total_cost: number
  reference_id?: string
  notes?: string
  created_by_user_id?: number
  created_at: string
}

interface Product {
  id: number
  name: string
  default_unit: string
  category_id: number
}

interface Category {
  id: number
  name: string
}

interface Location {
  id: number
  name: string
}

export function BeviStoqRestockHistory() {
  const [restocks, setRestocks] = useState<RestockRecord[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [locations, setLocations] = useState<Location[]>([])
  const [loading, setLoading] = useState(true)
  const [isAdding, setIsAdding] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)

  const [filters, setFilters] = useState({
    category_id: '',
    product_id: '',
    date_from: '',
    date_to: ''
  })

  const [formData, setFormData] = useState({
    product_id: '',
    location_id: '',
    quantity_restocked: '',
    unit: 'kg',
    restock_date: new Date().toISOString().split('T')[0],
    supplier: '',
    cost_per_unit: '',
    total_cost: '',
    reference_id: '',
    notes: ''
  })

  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    loadRestocks()
  }, [filters])

  const load = async () => {
    try {
      setLoading(true)
      const [cats, prods, locs] = await Promise.all([
        request<Category[]>('/api/bevi-stoq/categories?active_only=true&limit=1000'),
        request<Product[]>('/api/bevi-stoq/products?active_only=true&limit=1000'),
        request<Location[]>('/api/bevi-stoq/locations?active_only=true&limit=1000')
      ])
      setCategories(cats)
      setProducts(prods)
      setLocations(locs)
      await loadRestocks()
    } catch (error) {
      console.error('Load error:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadRestocks = async () => {
    try {
      const params = new URLSearchParams()
      if (filters.category_id) params.set('category_id', filters.category_id)
      if (filters.product_id) params.set('product_id', filters.product_id)
      if (filters.date_from) params.set('date_from', filters.date_from)
      if (filters.date_to) params.set('date_to', filters.date_to)
      params.set('limit', '500')

      const data = await request<RestockRecord[]>(`/api/bevi-stoq/restock-history?${params}`)
      setRestocks(data || [])
    } catch (error) {
      console.error('Load restocks error:', error)
    }
  }

  const handleSave = async () => {
    try {
      if (!formData.product_id || !formData.location_id || !formData.quantity_restocked) {
        alert('Fill all required fields')
        return
      }

      const payload = {
        product_id: parseInt(formData.product_id),
        location_id: parseInt(formData.location_id),
        quantity_restocked: parseFloat(formData.quantity_restocked),
        unit: formData.unit,
        restock_date: formData.restock_date,
        supplier: formData.supplier,
        cost_per_unit: parseFloat(formData.cost_per_unit) || 0,
        total_cost: parseFloat(formData.total_cost) || 0,
        reference_id: formData.reference_id || null,
        notes: formData.notes || null
      }

      if (isEditing && editingId) {
        await request(`/api/bevi-stoq/restock-history/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify(payload)
        })
      } else {
        await request('/api/bevi-stoq/restock-history', {
          method: 'POST',
          body: JSON.stringify(payload)
        })
      }

      setFormData({
        product_id: '', location_id: '', quantity_restocked: '', unit: 'kg',
        restock_date: new Date().toISOString().split('T')[0],
        supplier: '', cost_per_unit: '', total_cost: '', reference_id: '', notes: ''
      })
      setIsAdding(false)
      setIsEditing(false)
      setEditingId(null)
      await loadRestocks()
    } catch (error) {
      console.error('Error:', error)
    }
  }

  const handleEdit = (restock: RestockRecord) => {
    const product = products.find(p => p.id === restock.product_id)
    if (product) {
      setFormData({
        product_id: product.id.toString(),
        location_id: restock.location_id.toString(),
        quantity_restocked: restock.quantity_restocked.toString(),
        unit: restock.unit,
        restock_date: restock.restock_date,
        supplier: restock.supplier,
        cost_per_unit: restock.cost_per_unit.toString(),
        total_cost: restock.total_cost.toString(),
        reference_id: restock.reference_id || '',
        notes: restock.notes || ''
      })
      setEditingId(restock.id)
      setIsEditing(true)
      setIsAdding(true)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await request(`/api/bevi-stoq/restock-history/${id}`, { method: 'DELETE' })
      await loadRestocks()
    } catch (error) {
      console.error('Delete error:', error)
    }
  }

  const groupedByCategory = restocks.reduce((acc, record) => {
    if (!acc[record.category_name]) {
      acc[record.category_name] = []
    }
    acc[record.category_name].push(record)
    return acc
  }, {} as Record<string, RestockRecord[]>)

  const totalRestocked = restocks.reduce((sum, r) => sum + r.total_cost, 0)
  const totalQuantity = restocks.reduce((sum, r) => sum + r.quantity_restocked, 0)

  if (loading) return <Spinner label="Loading restock history..." />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-3xl text-latte">Restock History</h1>
        <Button onClick={() => { setIsAdding(true); setIsEditing(false); }}>+ Record Restock</Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <p className="text-xs text-latte/60">Total Restocks</p>
          <p className="mt-2 text-2xl font-bold text-gold">{restocks.length}</p>
        </Card>
        <Card>
          <p className="text-xs text-latte/60">Total Quantity</p>
          <p className="mt-2 text-2xl font-bold text-gold">{totalQuantity.toLocaleString()}</p>
        </Card>
        <Card>
          <p className="text-xs text-latte/60">Total Cost</p>
          <p className="mt-2 text-2xl font-bold text-gold">₹{totalRestocked.toLocaleString()}</p>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
            <Field label="Category">
              <Select
                value={filters.category_id}
                onChange={(e) => setFilters({ ...filters, category_id: e.target.value })}
                options={[
                  { value: '', label: 'All Categories' },
                  ...categories.map(c => ({ value: c.id.toString(), label: c.name }))
                ]}
              />
            </Field>

            <Field label="Product">
              <Select
                value={filters.product_id}
                onChange={(e) => setFilters({ ...filters, product_id: e.target.value })}
                options={[
                  { value: '', label: 'All Products' },
                  ...products.map(p => ({ value: p.id.toString(), label: p.name }))
                ]}
              />
            </Field>

            <Field label="From Date">
              <Input
                type="date"
                value={filters.date_from}
                onChange={(e) => setFilters({ ...filters, date_from: e.target.value })}
              />
            </Field>

            <Field label="To Date">
              <Input
                type="date"
                value={filters.date_to}
                onChange={(e) => setFilters({ ...filters, date_to: e.target.value })}
              />
            </Field>
          </div>
          <Button
            variant="ghost"
            onClick={() => setFilters({ category_id: '', product_id: '', date_from: '', date_to: '' })}
            className="w-full"
          >
            Reset Filters
          </Button>
        </div>
      </Card>

      {/* Grouped View by Category */}
      {Object.keys(groupedByCategory).length > 0 ? (
        <div className="space-y-6">
          {Object.entries(groupedByCategory).map(([category, categoryRestocks]) => (
            <div key={category}>
              <div className="mb-4 flex items-center gap-2">
                <h2 className="text-xl font-semibold text-latte">{category}</h2>
                <span className="text-xs text-latte/60">({categoryRestocks.length} restocks)</span>
              </div>

              <div className="space-y-3">
                {categoryRestocks.map((restock) => (
                  <Card key={restock.id} className="flex flex-col">
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <h3 className="font-semibold text-latte">{restock.product_name}</h3>
                        <div className="mt-2 flex gap-4 flex-wrap">
                          <div>
                            <p className="text-xs text-latte/60">Quantity</p>
                            <p className="text-sm font-medium text-gold">
                              {restock.quantity_restocked} {restock.unit}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs text-latte/60">Restock Date</p>
                            <p className="text-sm font-medium text-latte">
                              {new Date(restock.restock_date).toLocaleDateString()}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs text-latte/60">Location</p>
                            <p className="text-sm font-medium text-latte">{restock.location_name}</p>
                          </div>
                          <div>
                            <p className="text-xs text-latte/60">Supplier</p>
                            <p className="text-sm font-medium text-latte">{restock.supplier || 'N/A'}</p>
                          </div>
                          <div>
                            <p className="text-xs text-latte/60">Total Cost</p>
                            <p className="text-sm font-medium text-gold">₹{restock.total_cost.toLocaleString()}</p>
                          </div>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="ghost"
                          onClick={() => handleEdit(restock)}
                          icon={<Edit2 size={14} />}
                        >
                          Edit
                        </Button>
                        <Button
                          variant="danger"
                          onClick={() => setDeleteConfirm(restock.id)}
                          icon={<Trash2 size={14} />}
                        >
                          Delete
                        </Button>
                      </div>
                    </div>

                    {restock.notes && (
                      <div className="border-t border-caramel/15 pt-3 mt-3">
                        <p className="text-xs text-latte/60">Notes</p>
                        <p className="text-sm text-latte/70">{restock.notes}</p>
                      </div>
                    )}

                    <div className="border-t border-caramel/15 pt-3 mt-3 text-xs text-latte/50">
                      {restock.reference_id && (
                        <p>Reference: {restock.reference_id}</p>
                      )}
                      <p>Cost per unit: ₹{restock.cost_per_unit.toLocaleString()}</p>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          title="No restock records yet"
          hint={filters.category_id || filters.product_id ? 'Try adjusting your filters' : 'Start recording restock activities'}
          action={<Button onClick={() => setIsAdding(true)}>+ Record Restock</Button>}
        />
      )}

      {/* Add/Edit Modal */}
      <Modal
        open={isAdding}
        onClose={() => {
          setIsAdding(false)
          setIsEditing(false)
          setEditingId(null)
          setFormData({
            product_id: '', location_id: '', quantity_restocked: '', unit: 'kg',
            restock_date: new Date().toISOString().split('T')[0],
            supplier: '', cost_per_unit: '', total_cost: '', reference_id: '', notes: ''
          })
        }}
        title={isEditing ? 'Edit Restock Record' : 'Record Restock'}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault()
            handleSave()
          }}
          className="space-y-4"
        >
          <Field label="Product *">
            <Select
              value={formData.product_id}
              onChange={(e) => setFormData({ ...formData, product_id: e.target.value })}
              options={products.map(p => ({ value: p.id.toString(), label: p.name }))}
              required
            />
          </Field>

          <Field label="Location *">
            <Select
              value={formData.location_id}
              onChange={(e) => setFormData({ ...formData, location_id: e.target.value })}
              options={locations.map(l => ({ value: l.id.toString(), label: l.name }))}
              required
            />
          </Field>

          <Field label="Quantity Restocked *">
            <Input
              type="number"
              placeholder="e.g. 100"
              value={formData.quantity_restocked}
              onChange={(e) => setFormData({ ...formData, quantity_restocked: e.target.value })}
              required
            />
          </Field>

          <Field label="Unit *">
            <Select
              value={formData.unit}
              onChange={(e) => setFormData({ ...formData, unit: e.target.value })}
              options={[
                { value: 'kg', label: 'kg' },
                { value: 'g', label: 'g' },
                { value: 'pcs', label: 'pcs' },
                { value: 'litre', label: 'litre' },
                { value: 'box', label: 'box' },
                { value: 'bag', label: 'bag' }
              ]}
            />
          </Field>

          <Field label="Restock Date *">
            <Input
              type="date"
              value={formData.restock_date}
              onChange={(e) => setFormData({ ...formData, restock_date: e.target.value })}
              required
            />
          </Field>

          <Field label="Supplier">
            <Input
              placeholder="Supplier name"
              value={formData.supplier}
              onChange={(e) => setFormData({ ...formData, supplier: e.target.value })}
            />
          </Field>

          <Field label="Cost per Unit (₹)">
            <Input
              type="number"
              placeholder="0.00"
              value={formData.cost_per_unit}
              onChange={(e) => setFormData({ ...formData, cost_per_unit: e.target.value })}
              step="0.01"
            />
          </Field>

          <Field label="Total Cost (₹)">
            <Input
              type="number"
              placeholder="0.00"
              value={formData.total_cost}
              onChange={(e) => setFormData({ ...formData, total_cost: e.target.value })}
              step="0.01"
            />
          </Field>

          <Field label="Reference (Order/Invoice ID)">
            <Input
              placeholder="Reference number"
              value={formData.reference_id}
              onChange={(e) => setFormData({ ...formData, reference_id: e.target.value })}
            />
          </Field>

          <Field label="Notes">
            <Input
              placeholder="Any additional notes..."
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
            />
          </Field>

          <div className="flex gap-3">
            <Button
              variant="ghost"
              onClick={() => {
                setIsAdding(false)
                setIsEditing(false)
                setEditingId(null)
              }}
              type="button"
            >
              Cancel
            </Button>
            <Button type="submit" className="flex-1">
              {isEditing ? 'Update Restock' : 'Record Restock'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={deleteConfirm !== null}
        title="Delete Restock Record?"
        message="This restock record will be permanently deleted."
        confirmLabel="Delete"
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
