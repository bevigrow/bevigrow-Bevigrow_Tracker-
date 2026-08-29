import { Plus, CheckCircle, Clock } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api } from '../lib/api'
import { EmptyState, Spinner } from '../components/ui'
import { UnitSelect } from '../lib/units'

interface Restock {
  id: number
  product_id: number
  location_id: number
  quantity: number
  unit: string | null
  restock_date: string
  supplier_name: string | null
  cost_per_unit: number | null
  total_cost: number | null
  reference_id: string | null
  status: string
  created_at: string
}

interface Product {
  id: number
  name: string
}

interface Location {
  id: number
  name: string
}

export function BeviStoqRestocks() {
  const [restocks, setRestocks] = useState<Restock[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [locations, setLocations] = useState<Location[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({
    product_id: 0,
    location_id: 0,
    quantity: '',
    unit: '',
    restock_date: new Date().toISOString().split('T')[0],
    supplier_name: '',
    cost_per_unit: '',
    total_cost: '',
    reference_id: '',
  })
  const [filterStatus, setFilterStatus] = useState('')

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const [restRes, prodRes, locRes] = await Promise.all([
        api.get<Restock[]>('/api/bevi-stoq/restocks'),
        api.get<Product[]>('/api/bevi-stoq/products'),
        api.get<Location[]>('/api/bevi-stoq/locations'),
      ])
      setRestocks(restRes || [])
      setProducts(prodRes || [])
      setLocations(locRes || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load restocks')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: any) => {
    e.preventDefault()
    try {
      await api.post('/api/bevi-stoq/restocks', {
        product_id: parseInt(formData.product_id as any),
        location_id: parseInt(formData.location_id as any),
        quantity: parseFloat(formData.quantity),
        unit: formData.unit,
        restock_date: formData.restock_date,
        supplier_name: formData.supplier_name,
        cost_per_unit: formData.cost_per_unit ? parseFloat(formData.cost_per_unit) : null,
        total_cost: formData.total_cost ? parseFloat(formData.total_cost) : null,
        reference_id: formData.reference_id,
      })
      setFormData({
        product_id: 0,
        location_id: 0,
        quantity: '',
        unit: '',
        restock_date: new Date().toISOString().split('T')[0],
        supplier_name: '',
        cost_per_unit: '',
        total_cost: '',
        reference_id: '',
      })
      setShowForm(false)
      await fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create restock order')
    }
  }

  const handleReceive = async (id: number) => {
    try {
      await api.post(`/api/bevi-stoq/restocks/${id}/receive`, {})
      await fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to receive restock')
    }
  }

  const getProductName = (id: number) => products.find((p) => p.id === id)?.name || 'Unknown'
  const getLocationName = (id: number) => locations.find((l) => l.id === id)?.name || 'Unknown'

  let filtered = restocks
  if (filterStatus) filtered = filtered.filter((r) => r.status === filterStatus)

  if (loading) return <Spinner label="Loading restocks…" />
  if (error) return <EmptyState emoji="⚠️" title="Error" hint={error} />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-latte">Restock Orders</h1>
          <p className="mt-1 text-sm text-latte/60">Manage purchase orders and receipts</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 rounded-lg bg-gold/20 px-4 py-2 text-sm font-medium text-gold hover:bg-gold/30"
        >
          <Plus size={16} />
          New Order
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="rounded-lg border border-caramel/15 bg-espresso/40 p-6">
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-latte">Product *</label>
                <select
                  value={formData.product_id}
                  onChange={(e) => setFormData({ ...formData, product_id: parseInt(e.target.value) })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                  required
                >
                  <option value={0}>Select product</option>
                  {products.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-latte">Location *</label>
                <select
                  value={formData.location_id}
                  onChange={(e) => setFormData({ ...formData, location_id: parseInt(e.target.value) })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                  required
                >
                  <option value={0}>Select location</option>
                  {locations.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-latte">Quantity *</label>
                <input
                  type="number"
                  value={formData.quantity}
                  onChange={(e) => setFormData({ ...formData, quantity: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                  step="0.01"
                  required
                />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <UnitSelect
                value={formData.unit}
                onChange={(unit) => setFormData({ ...formData, unit })}
                label="Unit"
                required={false}
              />
              <div>
                <label className="block text-sm font-medium text-latte">Date *</label>
                <input
                  type="date"
                  value={formData.restock_date}
                  onChange={(e) => setFormData({ ...formData, restock_date: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-latte">Supplier</label>
                <input
                  type="text"
                  value={formData.supplier_name}
                  onChange={(e) => setFormData({ ...formData, supplier_name: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte placeholder-latte/40 focus:outline-none focus:ring-2 focus:ring-gold/50"
                  placeholder="Supplier name"
                />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-latte">Cost/Unit (₹)</label>
                <input
                  type="number"
                  value={formData.cost_per_unit}
                  onChange={(e) => setFormData({ ...formData, cost_per_unit: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                  step="0.01"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-latte">Total Cost (₹)</label>
                <input
                  type="number"
                  value={formData.total_cost}
                  onChange={(e) => setFormData({ ...formData, total_cost: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                  step="0.01"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-latte">Reference ID (PO)</label>
                <input
                  type="text"
                  value={formData.reference_id}
                  onChange={(e) => setFormData({ ...formData, reference_id: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte placeholder-latte/40 focus:outline-none focus:ring-2 focus:ring-gold/50"
                  placeholder="PO number"
                />
              </div>
            </div>
            <div className="flex gap-3">
              <button
                type="submit"
                className="rounded bg-gold/20 px-4 py-2 text-sm font-medium text-gold hover:bg-gold/30"
              >
                Create Order
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

      {/* Filter */}
      <select
        value={filterStatus}
        onChange={(e) => setFilterStatus(e.target.value)}
        className="rounded bg-bean/50 px-3 py-2 text-sm text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
      >
        <option value="">All Statuses</option>
        <option value="pending">Pending</option>
        <option value="received">Received</option>
        <option value="cancelled">Cancelled</option>
      </select>

      {filtered.length === 0 ? (
        <EmptyState emoji="📦" title="No restocks" hint="Create your first restock order" />
      ) : (
        <div className="space-y-3">
          {filtered.map((restock) => (
            <div key={restock.id} className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-4">
                  {restock.status === 'pending' ? (
                    <Clock size={20} className="mt-1 text-yellow-400" />
                  ) : (
                    <CheckCircle size={20} className="mt-1 text-green-400" />
                  )}
                  <div className="space-y-2">
                    <div>
                      <p className="font-semibold text-latte">{getProductName(restock.product_id)}</p>
                      <p className="text-xs text-latte/50">{getLocationName(restock.location_id)}</p>
                    </div>
                    {restock.supplier_name && <p className="text-xs text-latte/60">Supplier: {restock.supplier_name}</p>}
                    {restock.reference_id && <p className="text-xs text-latte/60">PO: {restock.reference_id}</p>}
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-lg font-bold text-gold">{restock.quantity} {restock.unit}</p>
                  {restock.total_cost && <p className="text-sm text-gold/60">₹{restock.total_cost}</p>}
                  <p className="text-xs text-latte/50">{new Date(restock.restock_date).toLocaleDateString()}</p>
                  {restock.status === 'pending' && (
                    <button
                      onClick={() => handleReceive(restock.id)}
                      className="mt-2 rounded bg-green-500/20 px-2 py-1 text-xs font-medium text-green-400 hover:bg-green-500/30"
                    >
                      Receive
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
