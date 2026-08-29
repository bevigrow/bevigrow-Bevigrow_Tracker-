import { AlertCircle, TrendingDown, AlertTriangle, Box } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api } from '../lib/api'
import { EmptyState, Spinner } from '../components/ui'

interface DashboardData {
  summary: {
    total_products: number
    low_stock_count: number
    out_of_stock_count: number
    total_locations: number
    total_categories: number
  }
  low_stock_products: Array<{
    product_id: number
    product_name: string
    status: string
    current_stock: number
    threshold: number
  }>
  out_of_stock_products: Array<{
    product_id: number
    product_name: string
    status: string
    current_stock: number
    threshold: number
  }>
  recent_movements: Array<{
    id: number
    product_id: number
    movement_type: string
    quantity: number
    unit: string | null
    created_at: string
  }>
}

export function BeviStoqDashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const response = await api.get<DashboardData>('/api/bevi-stoq/dashboard')
        setData(response)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load dashboard')
      } finally {
        setLoading(false)
      }
    }

    fetchDashboard()
  }, [])

  if (loading) return <Spinner label="Loading inventory dashboard…" />
  if (error) return <EmptyState emoji="⚠️" title="Error" hint={error} />
  if (!data) return <EmptyState emoji="📦" title="No data" hint="Start by adding products and stock" />

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-latte">Inventory Dashboard</h1>
        <p className="mt-1 text-sm text-latte/60">Real-time stock levels and alerts</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <SummaryCard
          label="Total Products"
          value={data.summary.total_products}
          icon="📦"
          color="bg-blue-500/10 text-blue-400"
        />
        <SummaryCard
          label="Total Locations"
          value={data.summary.total_locations}
          icon="📍"
          color="bg-purple-500/10 text-purple-400"
        />
        <SummaryCard
          label="Total Categories"
          value={data.summary.total_categories}
          icon="🏷️"
          color="bg-teal-500/10 text-teal-400"
        />
        <SummaryCard
          label="Low Stock"
          value={data.summary.low_stock_count}
          icon="⚠️"
          color="bg-yellow-500/10 text-yellow-400"
        />
        <SummaryCard
          label="Out of Stock"
          value={data.summary.out_of_stock_count}
          icon="🚨"
          color="bg-red-500/10 text-red-400"
        />
      </div>

      {/* Alerts Section */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Out of Stock */}
        <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-6">
          <div className="mb-4 flex items-center gap-2">
            <AlertCircle size={20} className="text-red-400" />
            <h2 className="font-semibold text-red-400">Out of Stock ({data.out_of_stock_products.length})</h2>
          </div>
          {data.out_of_stock_products.length === 0 ? (
            <p className="text-sm text-latte/60">All products in stock</p>
          ) : (
            <div className="space-y-2">
              {data.out_of_stock_products.map((product) => (
                <div key={product.product_id} className="flex items-center justify-between rounded bg-red-500/10 px-3 py-2 text-sm">
                  <span className="text-latte">{product.product_name}</span>
                  <span className="text-red-400">0 {product.threshold}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Low Stock */}
        <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-6">
          <div className="mb-4 flex items-center gap-2">
            <AlertTriangle size={20} className="text-yellow-400" />
            <h2 className="font-semibold text-yellow-400">Low Stock ({data.low_stock_products.length})</h2>
          </div>
          {data.low_stock_products.length === 0 ? (
            <p className="text-sm text-latte/60">No products below threshold</p>
          ) : (
            <div className="space-y-2">
              {data.low_stock_products.map((product) => (
                <div key={product.product_id} className="flex items-center justify-between rounded bg-yellow-500/10 px-3 py-2 text-sm">
                  <span className="text-latte">{product.product_name}</span>
                  <span className="text-yellow-400">{product.current_stock} / {product.threshold}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Recent Movements */}
      <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-6">
        <div className="mb-4 flex items-center gap-2">
          <TrendingDown size={20} className="text-gold" />
          <h2 className="font-semibold text-latte">Recent Stock Movements</h2>
        </div>
        {data.recent_movements.length === 0 ? (
          <p className="text-sm text-latte/60">No recent movements</p>
        ) : (
          <div className="space-y-3">
            {data.recent_movements.slice(0, 10).map((movement) => (
              <div key={movement.id} className="flex items-center justify-between border-b border-caramel/15 pb-3 last:border-0">
                <div className="flex items-center gap-3">
                  <Box size={16} className="text-gold/60" />
                  <div className="text-sm">
                    <p className="text-latte">{movement.movement_type.toUpperCase()}</p>
                    <p className="text-xs text-latte/50">{new Date(movement.created_at).toLocaleDateString()}</p>
                  </div>
                </div>
                <span className="text-sm font-medium text-gold">{movement.quantity} {movement.unit || 'units'}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function SummaryCard({ label, value, icon, color }: { label: string; value: number; icon: string; color: string }) {
  return (
    <div className={`rounded-lg border border-caramel/15 ${color} p-4`}>
      <p className="mb-2 text-2xl">{icon}</p>
      <p className="text-xs uppercase tracking-wide text-latte/60">{label}</p>
      <p className="mt-1 text-2xl font-bold text-latte">{value}</p>
    </div>
  )
}
