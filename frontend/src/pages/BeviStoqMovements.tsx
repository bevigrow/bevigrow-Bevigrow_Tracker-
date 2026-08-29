import { useEffect, useState } from 'react'
import { TrendingDown } from 'lucide-react'

import { api } from '../lib/api'
import { EmptyState, Spinner } from '../components/ui'

interface StockMovement {
  id: number
  product_id: number
  from_location_id: number | null
  to_location_id: number | null
  movement_type: string
  quantity: number
  unit: string | null
  created_at: string
  created_by_user_id: number
}

interface Product {
  id: number
  name: string
  default_unit: string
}

interface Location {
  id: number
  name: string
}

export function BeviStoqMovements() {
  const [movements, setMovements] = useState<StockMovement[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [locations, setLocations] = useState<Location[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterType, setFilterType] = useState('')

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const [movRes, prodRes, locRes] = await Promise.all([
        api.get<StockMovement[]>('/api/bevi-stoq/stock-movements'),
        api.get<Product[]>('/api/bevi-stoq/products'),
        api.get<Location[]>('/api/bevi-stoq/locations'),
      ])
      setMovements(movRes || [])
      setProducts(prodRes || [])
      setLocations(locRes || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load movements')
    } finally {
      setLoading(false)
    }
  }

  const getProductName = (id: number) => products.find((p) => p.id === id)?.name || 'Unknown'
  const getLocationName = (id: number | null) => (id ? locations.find((l) => l.id === id)?.name || 'Unknown' : '-')

  const movementTypes = ['receipt', 'transfer', 'adjustment', 'fulfillment', 'return']
  let filtered = movements
  if (filterType) filtered = filtered.filter((m) => m.movement_type === filterType)

  const getMovementColor = (type: string) => {
    switch (type) {
      case 'receipt':
        return 'bg-green-500/20 text-green-400'
      case 'transfer':
        return 'bg-blue-500/20 text-blue-400'
      case 'adjustment':
        return 'bg-yellow-500/20 text-yellow-400'
      case 'fulfillment':
        return 'bg-purple-500/20 text-purple-400'
      case 'return':
        return 'bg-orange-500/20 text-orange-400'
      default:
        return 'bg-latte/10 text-latte'
    }
  }

  if (loading) return <Spinner label="Loading movements…" />
  if (error) return <EmptyState emoji="⚠️" title="Error" hint={error} />

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-latte">Stock Audit Trail</h1>
        <p className="mt-1 text-sm text-latte/60">Complete history of all inventory movements</p>
      </div>

      {/* Filter */}
      <select
        value={filterType}
        onChange={(e) => setFilterType(e.target.value)}
        className="rounded bg-bean/50 px-3 py-2 text-sm text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
      >
        <option value="">All Movement Types</option>
        {movementTypes.map((type) => (
          <option key={type} value={type}>
            {type.charAt(0).toUpperCase() + type.slice(1)}
          </option>
        ))}
      </select>

      {filtered.length === 0 ? (
        <EmptyState emoji="📊" title="No movements" hint="Stock movements will appear here as you manage inventory" />
      ) : (
        <div className="space-y-3">
          {filtered.map((movement) => (
            <div key={movement.id} className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-4">
                  <TrendingDown size={20} className="mt-1 text-gold/60" />
                  <div className="space-y-1">
                    <p className="font-semibold text-latte">{getProductName(movement.product_id)}</p>
                    <div className="flex flex-wrap gap-2">
                      <span className={`inline-block rounded px-2 py-1 text-xs font-medium ${getMovementColor(movement.movement_type)}`}>
                        {movement.movement_type.toUpperCase()}
                      </span>
                      {movement.from_location_id && (
                        <span className="text-xs text-latte/50">FROM {getLocationName(movement.from_location_id)}</span>
                      )}
                      {movement.to_location_id && (
                        <span className="text-xs text-latte/50">TO {getLocationName(movement.to_location_id)}</span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-lg font-bold text-gold">
                    {movement.quantity} {movement.unit || 'units'}
                  </p>
                  <p className="text-xs text-latte/50">{new Date(movement.created_at).toLocaleDateString()}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
