import { Search, ChevronDown } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api } from '../lib/api'
import { EmptyState, Spinner } from '../components/ui'
import { useToast } from '../lib/toast'

interface StockMovement {
  id: number
  product_id: number
  product_name?: string
  movement_type: string
  quantity: number
  unit: string | null
  from_location_id?: number | null
  to_location_id?: number | null
  location_name?: string
  created_at: string
  created_by_user_id: number
  notes?: string | null
  reference_id?: number | null
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

export function BeviStoqHistory() {
  const [movements, setMovements] = useState<StockMovement[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [locations, setLocations] = useState<Location[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filters
  const [searchQuery, setSearchQuery] = useState('')
  const [dateFilter, setDateFilter] = useState<'today' | 'yesterday' | 'last3' | 'last7' | 'last30' | 'thisweek' | 'lastweek' | 'thismonth' | 'lastmonth' | 'custom'>('last7')
  const [customDateFrom, setCustomDateFrom] = useState<string>(new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0])
  const [customDateTo, setCustomDateTo] = useState<string>(new Date().toISOString().split('T')[0])
  const [activityTypeFilter, setActivityTypeFilter] = useState<string>('all')
  const [locationFilter, setLocationFilter] = useState<number | null>(null)
  const [productFilter, setProductFilter] = useState<number | null>(null)
  const [expandedDate, setExpandedDate] = useState<string | null>(null)

  useEffect(() => {
    fetchData()
  }, [dateFilter, customDateFrom, customDateTo, activityTypeFilter, locationFilter, productFilter, searchQuery])

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [movRes, prodRes, locRes] = await Promise.all([
        api.get<StockMovement[]>('/api/bevi-stoq/stock-movements'),
        api.get<Product[]>('/api/bevi-stoq/products'),
        api.get<Location[]>('/api/bevi-stoq/locations'),
      ])

      let filtered = movRes || []

      // Apply date filter
      const dateRange = getDateRange(dateFilter, customDateFrom, customDateTo)
      filtered = filtered.filter((m) => {
        const date = new Date(m.created_at)
        return date >= dateRange.from && date <= dateRange.to
      })

      // Apply activity type filter
      if (activityTypeFilter !== 'all') {
        filtered = filtered.filter((m) => m.movement_type === activityTypeFilter)
      }

      // Apply location filter
      if (locationFilter) {
        filtered = filtered.filter((m) => m.from_location_id === locationFilter || m.to_location_id === locationFilter)
      }

      // Apply product filter
      if (productFilter) {
        filtered = filtered.filter((m) => m.product_id === productFilter)
      }

      // Apply search
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        filtered = filtered.filter(
          (m) =>
            m.notes?.toLowerCase().includes(query) ||
            products.find((p) => p.id === m.product_id)?.name.toLowerCase().includes(query)
        )
      }

      // Sort by date descending
      filtered.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())

      setMovements(filtered)
      setProducts(prodRes || [])
      setLocations(locRes || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load history')
    } finally {
      setLoading(false)
    }
  }

  const getDateRange = (
    filter: string,
    customFrom: string,
    customTo: string
  ): { from: Date; to: Date } => {
    const today = new Date()
    today.setHours(0, 0, 0, 0)

    switch (filter) {
      case 'today':
        return { from: new Date(today), to: new Date(today.getTime() + 24 * 60 * 60 * 1000) }
      case 'yesterday':
        const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000)
        return { from: yesterday, to: new Date(today) }
      case 'last3':
        return { from: new Date(today.getTime() - 3 * 24 * 60 * 60 * 1000), to: new Date(today.getTime() + 24 * 60 * 60 * 1000) }
      case 'last7':
        return { from: new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000), to: new Date(today.getTime() + 24 * 60 * 60 * 1000) }
      case 'last30':
        return { from: new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000), to: new Date(today.getTime() + 24 * 60 * 60 * 1000) }
      case 'custom':
        return { from: new Date(customFrom), to: new Date(customTo + 'T23:59:59') }
      default:
        return { from: new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000), to: new Date(today.getTime() + 24 * 60 * 60 * 1000) }
    }
  }

  const groupByDate = (items: StockMovement[]) => {
    const groups: Record<string, StockMovement[]> = {}
    items.forEach((item) => {
      const date = new Date(item.created_at).toISOString().split('T')[0]
      if (!groups[date]) groups[date] = []
      groups[date].push(item)
    })
    return groups
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr + 'T00:00:00')
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000)

    if (date.getTime() === today.getTime()) return 'Today'
    if (date.getTime() === yesterday.getTime()) return 'Yesterday'
    return date.toLocaleDateString('en-IN', { year: 'numeric', month: 'long', day: 'numeric' })
  }

  const getActivityTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      stock_added: 'Stock Added',
      stock_removed: 'Stock Removed (Purchase)',
      transfer: 'Transfer',
      adjustment: 'Adjustment',
      opening_stock: 'Opening Stock',
      receipt: 'Receipt',
      fulfillment: 'Fulfillment',
      return: 'Return',
    }
    return labels[type] || type
  }

  const getProductName = (productId: number) => {
    return products.find((p) => p.id === productId)?.name || `Product ${productId}`
  }

  const getLocationName = (locationId: number) => {
    return locations.find((l) => l.id === locationId)?.name || `Location ${locationId}`
  }

  if (loading) return <Spinner label="Loading history…" />
  if (error) return <EmptyState emoji="⚠️" title="Error" hint={error} />

  const groupedMovements = groupByDate(movements)
  const totalTransactions = movements.length

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-latte">History</h1>
        <p className="mt-1 text-sm text-latte/60">Stock movements, purchases, transfers, and activities</p>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
          <p className="text-xs uppercase tracking-wide text-latte/60">Transactions</p>
          <p className="mt-2 text-2xl font-bold text-latte">{totalTransactions}</p>
        </div>
        <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
          <p className="text-xs uppercase tracking-wide text-latte/60">Stock Out</p>
          <p className="mt-2 text-2xl font-bold text-latte">
            {movements.filter((m) => m.movement_type === 'stock_removed').length}
          </p>
        </div>
        <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
          <p className="text-xs uppercase tracking-wide text-latte/60">Transfers</p>
          <p className="mt-2 text-2xl font-bold text-latte">
            {movements.filter((m) => m.movement_type === 'transfer').length}
          </p>
        </div>
        <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
          <p className="text-xs uppercase tracking-wide text-latte/60">Stock In</p>
          <p className="mt-2 text-2xl font-bold text-latte">
            {movements.filter((m) => m.movement_type === 'stock_added' || m.movement_type === 'opening_stock').length}
          </p>
        </div>
      </div>

      {/* Search */}
      <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
        <div className="relative">
          <Search size={18} className="absolute left-3 top-3 text-latte/60" />
          <input
            type="text"
            placeholder="Search by product, customer, notes..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded bg-bean/50 pl-10 pr-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
          />
        </div>
      </div>

      {/* Filters */}
      <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-4 space-y-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label className="block text-xs font-medium text-latte/60 mb-1">Date Range</label>
            <select
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value as any)}
              className="w-full rounded bg-bean/50 px-3 py-2 text-sm text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
            >
              <option value="today">Today</option>
              <option value="yesterday">Yesterday</option>
              <option value="last3">Last 3 Days</option>
              <option value="last7">Last 7 Days</option>
              <option value="last30">Last 30 Days</option>
              <option value="custom">Custom Range</option>
            </select>
          </div>

          {dateFilter === 'custom' && (
            <>
              <div>
                <label className="block text-xs font-medium text-latte/60 mb-1">From</label>
                <input
                  type="date"
                  value={customDateFrom}
                  onChange={(e) => setCustomDateFrom(e.target.value)}
                  className="w-full rounded bg-bean/50 px-3 py-2 text-sm text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-latte/60 mb-1">To</label>
                <input
                  type="date"
                  value={customDateTo}
                  onChange={(e) => setCustomDateTo(e.target.value)}
                  className="w-full rounded bg-bean/50 px-3 py-2 text-sm text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                />
              </div>
            </>
          )}

          <div>
            <label className="block text-xs font-medium text-latte/60 mb-1">Activity Type</label>
            <select
              value={activityTypeFilter}
              onChange={(e) => setActivityTypeFilter(e.target.value)}
              className="w-full rounded bg-bean/50 px-3 py-2 text-sm text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
            >
              <option value="all">All Activities</option>
              <option value="stock_removed">Purchases</option>
              <option value="transfer">Transfers</option>
              <option value="stock_added">Stock Added</option>
              <option value="adjustment">Adjustments</option>
              <option value="opening_stock">Opening Stock</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-latte/60 mb-1">Location</label>
            <select
              value={locationFilter || ''}
              onChange={(e) => setLocationFilter(e.target.value ? parseInt(e.target.value) : null)}
              className="w-full rounded bg-bean/50 px-3 py-2 text-sm text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
            >
              <option value="">All Locations</option>
              {locations.map((loc) => (
                <option key={loc.id} value={loc.id}>
                  {loc.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-latte/60 mb-1">Product</label>
            <select
              value={productFilter || ''}
              onChange={(e) => setProductFilter(e.target.value ? parseInt(e.target.value) : null)}
              className="w-full rounded bg-bean/50 px-3 py-2 text-sm text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
            >
              <option value="">All Products</option>
              {products.map((prod) => (
                <option key={prod.id} value={prod.id}>
                  {prod.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* History List */}
      {Object.keys(groupedMovements).length === 0 ? (
        <EmptyState emoji="📋" title="No history" hint="No activities match your filters" />
      ) : (
        <div className="space-y-4">
          {Object.entries(groupedMovements)
            .sort(([dateA], [dateB]) => new Date(dateB).getTime() - new Date(dateA).getTime())
            .map(([date, items]) => (
              <div key={date} className="rounded-lg border border-caramel/15 bg-espresso/40 overflow-hidden">
                <button
                  onClick={() => setExpandedDate(expandedDate === date ? null : date)}
                  className="w-full px-6 py-3 flex items-center justify-between hover:bg-bean/20 transition"
                >
                  <div>
                    <h3 className="font-semibold text-latte">{formatDate(date)}</h3>
                    <p className="text-xs text-latte/60 mt-1">{items.length} transactions</p>
                  </div>
                  <ChevronDown
                    size={20}
                    className={`text-latte/60 transition ${expandedDate === date ? 'rotate-180' : ''}`}
                  />
                </button>

                {expandedDate === date && (
                  <div className="border-t border-caramel/15 divide-y divide-caramel/15">
                    {items.map((movement) => (
                      <div
                        key={movement.id}
                        className="px-6 py-3 hover:bg-bean/20 transition text-sm"
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-latte">{getActivityTypeLabel(movement.movement_type)}</span>
                              <span className="text-xs text-latte/50">{getProductName(movement.product_id)}</span>
                            </div>
                            <div className="flex gap-4 mt-1 text-xs text-latte/60">
                              <span>
                                {movement.quantity} {movement.unit}
                              </span>
                              {movement.from_location_id && movement.to_location_id && (
                                <span>
                                  {getLocationName(movement.from_location_id)} → {getLocationName(movement.to_location_id)}
                                </span>
                              )}
                              {movement.from_location_id && !movement.to_location_id && (
                                <span>{getLocationName(movement.from_location_id)}</span>
                              )}
                              {movement.notes && <span>{movement.notes}</span>}
                            </div>
                          </div>
                          <div className="text-right text-xs text-latte/60">
                            {new Date(movement.created_at).toLocaleTimeString('en-IN')}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
        </div>
      )}
    </div>
  )
}
