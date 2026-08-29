import { useEffect, useState } from 'react'
import { AlertCircle } from 'lucide-react'

import { api } from '../lib/api'
import { EmptyState, Spinner } from '../components/ui'

interface InventoryItem {
  id: number
  product_id: number
  location_id: number
  physical_stock: number
  reserved_stock: number
  available_stock: number
}

interface Product {
  id: number
  name: string
  default_unit: string
  low_stock_threshold: number
}

interface Location {
  id: number
  name: string
}

export function BeviStoqInventory() {
  const [inventory, setInventory] = useState<InventoryItem[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [locations, setLocations] = useState<Location[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterProduct, setFilterProduct] = useState(0)
  const [filterLocation, setFilterLocation] = useState(0)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const [invRes, prodRes, locRes] = await Promise.all([
        api.get<InventoryItem[]>('/api/bevi-stoq/inventory'),
        api.get<Product[]>('/api/bevi-stoq/products'),
        api.get<Location[]>('/api/bevi-stoq/locations'),
      ])
      setInventory(invRes || [])
      setProducts(prodRes || [])
      setLocations(locRes || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load inventory')
    } finally {
      setLoading(false)
    }
  }

  const getProductName = (id: number) => products.find((p) => p.id === id)?.name || 'Unknown'
  const getProductUnit = (id: number) => products.find((p) => p.id === id)?.default_unit || ''
  const getProductThreshold = (id: number) => products.find((p) => p.id === id)?.low_stock_threshold || 0
  const getLocationName = (id: number) => locations.find((l) => l.id === id)?.name || 'Unknown'
  const getStockStatus = (availableStock: number, threshold: number) => {
    if (availableStock <= 0) return { label: 'OUT OF STOCK', color: 'bg-red-500/20 text-red-400' }
    if (availableStock <= threshold) return { label: 'LOW STOCK', color: 'bg-yellow-500/20 text-yellow-400' }
    return { label: 'NORMAL', color: 'bg-green-500/20 text-green-400' }
  }

  let filtered = inventory
  if (filterProduct) filtered = filtered.filter((i) => i.product_id === filterProduct)
  if (filterLocation) filtered = filtered.filter((i) => i.location_id === filterLocation)

  if (loading) return <Spinner label="Loading inventory…" />
  if (error) return <EmptyState emoji="⚠️" title="Error" hint={error} />

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-latte">Stock Levels</h1>
        <p className="mt-1 text-sm text-latte/60">Physical stock, reserved, and available quantities</p>
      </div>

      {/* Filters */}
      <div className="flex gap-4">
        <select
          value={filterProduct}
          onChange={(e) => setFilterProduct(parseInt(e.target.value))}
          className="rounded bg-bean/50 px-3 py-2 text-sm text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
        >
          <option value={0}>All Products</option>
          {products.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <select
          value={filterLocation}
          onChange={(e) => setFilterLocation(parseInt(e.target.value))}
          className="rounded bg-bean/50 px-3 py-2 text-sm text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
        >
          <option value={0}>All Locations</option>
          {locations.map((l) => (
            <option key={l.id} value={l.id}>
              {l.name}
            </option>
          ))}
        </select>
      </div>

      {filtered.length === 0 ? (
        <EmptyState emoji="📦" title="No stock" hint="Add products and locations to start tracking inventory" />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-caramel/15">
          <table className="w-full">
            <thead>
              <tr className="border-b border-caramel/15 bg-espresso/60">
                <th className="px-4 py-3 text-left text-sm font-semibold text-latte">Product</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-latte">Location</th>
                <th className="px-4 py-3 text-right text-sm font-semibold text-latte">Physical</th>
                <th className="px-4 py-3 text-right text-sm font-semibold text-latte">Reserved</th>
                <th className="px-4 py-3 text-right text-sm font-semibold text-latte">Available</th>
                <th className="px-4 py-3 text-center text-sm font-semibold text-latte">Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => {
                const unit = getProductUnit(item.product_id)
                const threshold = getProductThreshold(item.product_id)
                const status = getStockStatus(item.available_stock, threshold)
                return (
                  <tr key={item.id} className="border-b border-caramel/15 hover:bg-espresso/40">
                    <td className="px-4 py-3 text-sm text-latte">{getProductName(item.product_id)}</td>
                    <td className="px-4 py-3 text-sm text-latte/70">{getLocationName(item.location_id)}</td>
                    <td className="px-4 py-3 text-right text-sm text-latte">
                      {item.physical_stock} {unit}
                    </td>
                    <td className="px-4 py-3 text-right text-sm text-latte/70">
                      {item.reserved_stock} {unit}
                    </td>
                    <td className="px-4 py-3 text-right text-sm font-medium text-gold">
                      {item.available_stock} {unit}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className={`inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium ${status.color}`}>
                        {status.label === 'OUT OF STOCK' && <AlertCircle size={12} />}
                        {status.label}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
