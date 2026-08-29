import { Plus } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api } from '../lib/api'
import { EmptyState, Spinner } from '../components/ui'

interface Requirement {
  id: number
  contact_id: number | null
  customer_name: string
  status: string
  created_at: string
  items: Array<{
    id: number
    product_id: number
    quantity_required: number
    quantity_reserved: number
    quantity_fulfilled: number
    unit: string | null
  }>
}

interface Product {
  id: number
  name: string
}

export function BeviStoqRequirements() {
  const [requirements, setRequirements] = useState<Requirement[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({
    customer_name: '',
    contact_id: '',
    items: [{ product_id: 0, quantity_required: '' }],
  })

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const [reqRes, prodRes] = await Promise.all([
        api.get<Requirement[]>('/api/bevi-stoq/customer-requirements'),
        api.get<Product[]>('/api/bevi-stoq/products'),
      ])
      setRequirements(reqRes || [])
      setProducts(prodRes || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load requirements')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: any) => {
    e.preventDefault()
    try {
      await api.post('/api/bevi-stoq/customer-requirements', {
        customer_name: formData.customer_name,
        contact_id: formData.contact_id ? parseInt(formData.contact_id) : null,
        items: formData.items.map((item) => ({
          product_id: item.product_id,
          quantity_required: parseFloat(item.quantity_required),
        })),
      })
      setFormData({
        customer_name: '',
        contact_id: '',
        items: [{ product_id: 0, quantity_required: '' }],
      })
      setShowForm(false)
      await fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create requirement')
    }
  }

  const handleReserve = async (id: number) => {
    try {
      await api.post(`/api/bevi-stoq/customer-requirements/${id}/reserve`, {})
      await fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reserve requirement')
    }
  }

  const handleFulfill = async (id: number) => {
    try {
      await api.post(`/api/bevi-stoq/customer-requirements/${id}/fulfill`, {})
      await fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fulfill requirement')
    }
  }

  const handleCancel = async (id: number) => {
    try {
      await api.post(`/api/bevi-stoq/customer-requirements/${id}/cancel`, {})
      await fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel requirement')
    }
  }

  const getProductName = (id: number) => products.find((p) => p.id === id)?.name || 'Unknown'

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending':
        return 'bg-yellow-500/20 text-yellow-400'
      case 'reserved':
        return 'bg-blue-500/20 text-blue-400'
      case 'fulfilled':
        return 'bg-green-500/20 text-green-400'
      case 'completed':
        return 'bg-purple-500/20 text-purple-400'
      case 'cancelled':
        return 'bg-red-500/20 text-red-400'
      default:
        return 'bg-latte/10 text-latte'
    }
  }

  if (loading) return <Spinner label="Loading requirements…" />
  if (error) return <EmptyState emoji="⚠️" title="Error" hint={error} />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-latte">Customer Requirements</h1>
          <p className="mt-1 text-sm text-latte/60">Track customer product orders</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 rounded-lg bg-gold/20 px-4 py-2 text-sm font-medium text-gold hover:bg-gold/30"
        >
          <Plus size={16} />
          New Requirement
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="rounded-lg border border-caramel/15 bg-espresso/40 p-6">
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-latte">Customer Name *</label>
                <input
                  type="text"
                  value={formData.customer_name}
                  onChange={(e) => setFormData({ ...formData, customer_name: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte placeholder-latte/40 focus:outline-none focus:ring-2 focus:ring-gold/50"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-latte">Contact ID</label>
                <input
                  type="number"
                  value={formData.contact_id}
                  onChange={(e) => setFormData({ ...formData, contact_id: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte placeholder-latte/40 focus:outline-none focus:ring-2 focus:ring-gold/50"
                />
              </div>
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
                      value={item.quantity_required}
                      onChange={(e) => {
                        const newItems = [...formData.items]
                        newItems[idx].quantity_required = e.target.value
                        setFormData({ ...formData, items: newItems })
                      }}
                      className="w-24 rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                      placeholder="Qty"
                      step="0.01"
                      required
                    />
                  </div>
                ))}
              </div>
              <button
                type="button"
                onClick={() => setFormData({ ...formData, items: [...formData.items, { product_id: 0, quantity_required: '' }] })}
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
                Create Requirement
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

      {requirements.length === 0 ? (
        <EmptyState emoji="📋" title="No requirements" hint="Create your first customer requirement" />
      ) : (
        <div className="space-y-4">
          {requirements.map((req) => (
            <div key={req.id} className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
              <div className="mb-3 flex items-start justify-between">
                <div>
                  <p className="font-semibold text-latte">{req.customer_name}</p>
                  <p className="text-xs text-latte/50">{new Date(req.created_at).toLocaleDateString()}</p>
                </div>
                <span className={`inline-block rounded px-2 py-1 text-xs font-medium ${getStatusColor(req.status)}`}>
                  {req.status.toUpperCase()}
                </span>
              </div>
              <div className="mb-4 space-y-1">
                {req.items.map((item) => (
                  <div key={item.id} className="flex items-center justify-between text-sm">
                    <span className="text-latte/70">{getProductName(item.product_id)}</span>
                    <span className="text-latte/50">
                      {item.quantity_fulfilled} / {item.quantity_required} fulfilled
                    </span>
                  </div>
                ))}
              </div>
              <div className="flex gap-2">
                {req.status === 'pending' && (
                  <button
                    onClick={() => handleReserve(req.id)}
                    className="text-xs font-medium rounded px-2 py-1 bg-blue-500/20 text-blue-400 hover:bg-blue-500/30"
                  >
                    Reserve
                  </button>
                )}
                {req.status === 'reserved' && (
                  <button
                    onClick={() => handleFulfill(req.id)}
                    className="text-xs font-medium rounded px-2 py-1 bg-green-500/20 text-green-400 hover:bg-green-500/30"
                  >
                    Fulfill
                  </button>
                )}
                {(req.status === 'pending' || req.status === 'reserved') && (
                  <button
                    onClick={() => handleCancel(req.id)}
                    className="text-xs font-medium rounded px-2 py-1 bg-red-500/20 text-red-400 hover:bg-red-500/30"
                  >
                    Cancel
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
