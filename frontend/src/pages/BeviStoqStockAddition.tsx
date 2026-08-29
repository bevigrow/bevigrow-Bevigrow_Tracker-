import { Plus } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api } from '../lib/api'
import { EmptyState, Spinner, useToast } from '../components/ui'

interface Product {
  id: number
  name: string
  default_unit: string
}

interface Location {
  id: number
  name: string
}

export function BeviStoqStockAddition() {
  const toast = useToast()
  const [products, setProducts] = useState<Product[]>([])
  const [locations, setLocations] = useState<Location[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({
    product_id: 0,
    quantity: '',
    unit: '',
    location_id: 0,
    stock_date: new Date().toISOString().split('T')[0],
    notes: '',
  })
  const [submissions, setSubmissions] = useState<any[]>([])

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const [prodRes, locRes] = await Promise.all([
        api.get<Product[]>('/api/bevi-stoq/products'),
        api.get<Location[]>('/api/bevi-stoq/locations'),
      ])
      setProducts(prodRes || [])
      setLocations(locRes || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: any) => {
    e.preventDefault()
    try {
      await api.post('/api/bevi-stoq/stock-movements', {
        product_id: parseInt(formData.product_id as any),
        to_location_id: parseInt(formData.location_id as any),
        movement_type: 'stock_added',
        quantity: parseFloat(formData.quantity),
        unit: formData.unit,
        reference_id: 0,
        notes: formData.notes || 'Stock added',
      })
      setFormData({
        product_id: 0,
        quantity: '',
        unit: '',
        location_id: 0,
        stock_date: new Date().toISOString().split('T')[0],
        notes: '',
      })
      setShowForm(false)
      setError(null)
      toast.success('Stock added successfully')
      fetchData()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to add stock'
      setError(message)
      toast.error(message)
    }
  }

  const getProductName = (id: number) => products.find((p) => p.id === id)?.name || 'Unknown'
  const getLocationName = (id: number) => locations.find((l) => l.id === id)?.name || 'Unknown'

  if (loading) return <Spinner label="Loading…" />
  if (error && !showForm) return <EmptyState emoji="⚠️" title="Error" hint={error} />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-latte">Add Stock</h1>
          <p className="mt-1 text-sm text-latte/60">Receive and add inventory to locations</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 rounded-lg bg-gold/20 px-4 py-2 text-sm font-medium text-gold hover:bg-gold/30"
        >
          <Plus size={16} />
          Add Stock
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="rounded-lg border border-caramel/15 bg-espresso/40 p-6">
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-latte">Product *</label>
                <select
                  value={formData.product_id}
                  onChange={(e) => {
                    const prodId = parseInt(e.target.value)
                    const prod = products.find((p) => p.id === prodId)
                    setFormData({
                      ...formData,
                      product_id: prodId,
                      unit: prod?.default_unit || '',
                    })
                  }}
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
                <label className="block text-sm font-medium text-latte">Quantity *</label>
                <input
                  type="number"
                  value={formData.quantity}
                  onChange={(e) => setFormData({ ...formData, quantity: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                  placeholder="Enter quantity"
                  step="0.01"
                  required
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-latte">Unit *</label>
                <input
                  type="text"
                  value={formData.unit}
                  onChange={(e) => setFormData({ ...formData, unit: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte placeholder-latte/40 focus:outline-none focus:ring-2 focus:ring-gold/50"
                  placeholder="e.g., kg, L"
                  required
                />
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
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-latte">Stock Date *</label>
                <input
                  type="date"
                  value={formData.stock_date}
                  onChange={(e) => setFormData({ ...formData, stock_date: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-latte">Notes</label>
                <input
                  type="text"
                  value={formData.notes}
                  onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte placeholder-latte/40 focus:outline-none focus:ring-2 focus:ring-gold/50"
                  placeholder="Optional notes"
                />
              </div>
            </div>
            <div className="flex gap-3">
              <button
                type="submit"
                className="rounded bg-gold/20 px-4 py-2 text-sm font-medium text-gold hover:bg-gold/30"
              >
                Add Stock
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

      <EmptyState emoji="📦" title="Ready to add stock" hint="Click 'Add Stock' to start receiving inventory" />
    </div>
  )
}
