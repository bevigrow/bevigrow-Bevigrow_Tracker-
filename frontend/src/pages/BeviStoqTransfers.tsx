import { Plus } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api } from '../lib/api'
import { EmptyState, Spinner } from '../components/ui'
import { useToast } from '../lib/toast'

interface Location {
  id: number
  name: string
}

interface Product {
  id: number
  name: string
  default_unit: string
}

interface Inventory {
  id: number
  product_id: number
  location_id: number
  physical_stock: number
  reserved_stock: number
}

interface TransferLine {
  product_id: number
  from_location_id: number
  to_location_id: number
  quantity: string
  unit: string
}

export function BeviStoqTransfers() {
  const toast = useToast()
  const [locations, setLocations] = useState<Location[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [inventory, setInventory] = useState<Inventory[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [transferLines, setTransferLines] = useState<TransferLine[]>([
    { product_id: 0, from_location_id: 0, to_location_id: 0, quantity: '', unit: '' }
  ])

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const [locRes, prodRes, invRes] = await Promise.all([
        api.get<Location[]>('/api/bevi-stoq/locations'),
        api.get<Product[]>('/api/bevi-stoq/products'),
        api.get<Inventory[]>('/api/bevi-stoq/inventory'),
      ])
      setLocations(locRes || [])
      setProducts(prodRes || [])
      setInventory(invRes || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  const getAvailableStock = (productId: number, locationId: number) => {
    const inv = inventory.find(i => i.product_id === productId && i.location_id === locationId)
    return inv ? inv.physical_stock - inv.reserved_stock : 0
  }

  const getProductUnit = (productId: number) => {
    return products.find(p => p.id === productId)?.default_unit || ''
  }

  const handleSubmit = async (e: any) => {
    e.preventDefault()
    if (submitting) return
    setSubmitting(true)
    setError(null)

    try {
      // Validate all lines
      for (const line of transferLines) {
        if (!line.product_id || !line.from_location_id || !line.to_location_id || !line.quantity) {
          setError('All transfer lines must be complete')
          setSubmitting(false)
          return
        }
        if (parseFloat(line.quantity) <= 0) {
          setError('Quantity must be positive')
          setSubmitting(false)
          return
        }
        if (line.from_location_id === line.to_location_id) {
          setError('Source and destination locations must be different')
          setSubmitting(false)
          return
        }
      }

      // Execute all transfers
      for (const line of transferLines) {
        await api.post('/api/bevi-stoq/transfers', {
          from_location_id: line.from_location_id,
          to_location_id: line.to_location_id,
          product_id: line.product_id,
          quantity: parseFloat(line.quantity),
          unit: line.unit || null,
          notes: `Stock transfer from ${locations.find(l => l.id === line.from_location_id)?.name} to ${locations.find(l => l.id === line.to_location_id)?.name}`
        })
      }

      toast.success('Transfer completed successfully')
      setTransferLines([{ product_id: 0, from_location_id: 0, to_location_id: 0, quantity: '', unit: '' }])
      setShowForm(false)
      await fetchData()
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Transfer failed'
      setError(msg)
      toast.error(msg)
    } finally {
      setSubmitting(false)
    }
  }

  const addLine = () => {
    setTransferLines([...transferLines, { product_id: 0, from_location_id: 0, to_location_id: 0, quantity: '', unit: '' }])
  }

  const removeLine = (idx: number) => {
    setTransferLines(transferLines.filter((_, i) => i !== idx))
  }

  const updateLine = (idx: number, updates: Partial<TransferLine>) => {
    const newLines = [...transferLines]
    newLines[idx] = { ...newLines[idx], ...updates }
    setTransferLines(newLines)
  }

  if (loading) return <Spinner label="Loading transfers…" />
  if (error && !showForm) return <EmptyState emoji="⚠️" title="Error" hint={error} />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-latte">Stock Transfer</h1>
          <p className="mt-1 text-sm text-latte/60">Move inventory between locations</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 rounded-lg bg-gold/20 px-4 py-2 text-sm font-medium text-gold hover:bg-gold/30"
        >
          <Plus size={16} />
          New Transfer
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="rounded-lg border border-caramel/15 bg-espresso/40 p-6">
          <div className="mb-4 pb-4 border-b border-caramel/15">
            <h2 className="text-lg font-semibold text-latte">Create Stock Transfer</h2>
            <p className="text-xs text-latte/60 mt-1">Move products between locations atomically</p>
          </div>
          {error && (
            <div className="mb-4 rounded-lg bg-red-500/20 p-4 text-red-400">
              <p className="text-sm font-medium">Error: {error}</p>
            </div>
          )}

          <div className="space-y-4">
            {transferLines.map((line, idx) => (
              <div key={idx} className="rounded-lg border border-caramel/15 bg-bean/20 p-4">
                <div className="grid grid-cols-2 gap-3 mb-3">
                  <div>
                    <label className="block text-xs font-medium text-latte/60 mb-1">From Location</label>
                    <select
                      value={line.from_location_id}
                      onChange={(e) => updateLine(idx, { from_location_id: parseInt(e.target.value) })}
                      className="w-full rounded bg-bean/50 px-3 py-2 text-sm text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                      required
                    >
                      <option value={0}>Select location</option>
                      {locations.map((loc) => (
                        <option key={loc.id} value={loc.id}>
                          {loc.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-latte/60 mb-1">To Location</label>
                    <select
                      value={line.to_location_id}
                      onChange={(e) => updateLine(idx, { to_location_id: parseInt(e.target.value) })}
                      className="w-full rounded bg-bean/50 px-3 py-2 text-sm text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                      required
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

                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-latte/60 mb-1">Product</label>
                    <select
                      value={line.product_id}
                      onChange={(e) => {
                        const pid = parseInt(e.target.value)
                        updateLine(idx, { product_id: pid, unit: getProductUnit(pid) })
                      }}
                      className="w-full rounded bg-bean/50 px-3 py-2 text-sm text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
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
                    <label className="block text-xs font-medium text-latte/60 mb-1">Quantity</label>
                    <input
                      type="number"
                      step="0.01"
                      value={line.quantity}
                      onChange={(e) => updateLine(idx, { quantity: e.target.value })}
                      className="w-full rounded bg-bean/50 px-3 py-2 text-sm text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                      placeholder="Qty"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-latte/60 mb-1">Unit</label>
                    <input
                      type="text"
                      value={line.unit}
                      disabled
                      className="w-full rounded bg-bean/50 px-3 py-2 text-sm text-latte/50 focus:outline-none"
                    />
                  </div>
                </div>
                {line.product_id > 0 && line.from_location_id > 0 && (
                  <div className="mt-2 text-xs text-latte/60">
                    Available: {getAvailableStock(line.product_id, line.from_location_id).toFixed(2)} {getProductUnit(line.product_id)}
                  </div>
                )}
                <button
                  type="button"
                  onClick={() => removeLine(idx)}
                  className="mt-3 text-xs text-red-400 hover:text-red-300"
                >
                  Remove line
                </button>
              </div>
            ))}

            <button
              type="button"
              onClick={addLine}
              className="text-sm text-gold hover:text-gold/80"
            >
              + Add Product
            </button>

            <div className="flex gap-3 pt-4">
              <button
                type="submit"
                disabled={submitting}
                className="rounded bg-gold/20 px-4 py-2 text-sm font-medium text-gold hover:bg-gold/30 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? 'Transferring...' : 'Execute Transfer'}
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

      <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-6">
        <h3 className="text-lg font-semibold text-latte mb-4">Location Stock Levels</h3>
        <div className="grid grid-cols-2 gap-6">
          {locations.map((loc) => (
            <div key={loc.id} className="rounded-lg border border-caramel/15 bg-bean/20 p-4">
              <h4 className="font-semibold text-latte mb-3">{loc.name}</h4>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {inventory
                  .filter((inv) => inv.location_id === loc.id)
                  .map((inv) => {
                    const prod = products.find(p => p.id === inv.product_id)
                    const available = inv.physical_stock - inv.reserved_stock
                    return (
                      <div key={inv.id} className="flex justify-between text-sm text-latte/70">
                        <span>{prod?.name}</span>
                        <span className={available > 0 ? 'text-green-400' : 'text-red-400'}>
                          {available.toFixed(2)} {prod?.default_unit}
                        </span>
                      </div>
                    )
                  })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
