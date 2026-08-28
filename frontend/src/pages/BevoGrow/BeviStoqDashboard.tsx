import { Package, AlertCircle, ShoppingCart, TrendingDown } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { request } from '../../lib/api'
import { Card, Button, Spinner, EmptyState, cx } from '../../components/ui'

interface DashboardData {
  summary: {
    total_stock_value: number
    low_stock_count: number
    out_of_stock_count: number
    pending_requirements_count: number
  }
  stock_by_category: Array<{
    category_id: number
    category_name: string
    total_quantity: number
    product_count: number
  }>
  stock_by_location: Array<{
    location_id: number
    location_name: string
    total_quantity: number
    product_count: number
  }>
  recent_movements: Array<{
    id: number
    product_name: string
    location_name: string
    movement_type: string
    quantity: number
    unit: string
    created_at: string
    created_by_name?: string
  }>
}

export function BeviStoqDashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    load()
  }, [])

  const load = async () => {
    try {
      setLoading(true)
      const dashboard = await request<DashboardData>('/api/bevi-stoq/dashboard')
      setData(dashboard)
    } catch (error) {
      console.error('Failed to load dashboard:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <Spinner label="Loading inventory dashboard..." />
  }

  if (!data) {
    return (
      <EmptyState
        title="Dashboard Error"
        hint="Failed to load inventory data. Please refresh the page."
        action={<Button onClick={load}>Try Again</Button>}
      />
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-3xl text-latte">Bevi Stoq</h1>
          <p className="mt-1 text-sm text-latte/50">Inventory Management Dashboard</p>
        </div>
        <Link to="/app/bevi-stoq/products">
          <Button>+ Add Stock</Button>
        </Link>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Total Stock */}
        <Card>
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-latte/60">Total Stock</p>
              <p className="mt-2 text-3xl font-bold text-gold">
                {data.summary.total_stock_value.toLocaleString()}
              </p>
            </div>
            <div className="rounded-lg bg-gold/10 p-3">
              <Package className="text-gold" size={20} />
            </div>
          </div>
        </Card>

        {/* Low Stock */}
        <Card>
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-latte/60">Low Stock</p>
              <p className="mt-2 text-3xl font-bold text-orange-400">
                {data.summary.low_stock_count}
              </p>
            </div>
            <div className="rounded-lg bg-orange-400/10 p-3">
              <TrendingDown className="text-orange-400" size={20} />
            </div>
          </div>
        </Card>

        {/* Out of Stock */}
        <Card>
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-latte/60">Out of Stock</p>
              <p className={cx('mt-2 text-3xl font-bold', data.summary.out_of_stock_count > 0 ? 'text-red-400' : 'text-latte')}>
                {data.summary.out_of_stock_count}
              </p>
            </div>
            <div className={cx('rounded-lg p-3', data.summary.out_of_stock_count > 0 ? 'bg-red-400/10' : 'bg-latte/10')}>
              <AlertCircle className={data.summary.out_of_stock_count > 0 ? 'text-red-400' : 'text-latte/40'} size={20} />
            </div>
          </div>
        </Card>

        {/* Pending Requirements */}
        <Card>
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-latte/60">Pending Requirements</p>
              <p className="mt-2 text-3xl font-bold text-sky-400">
                {data.summary.pending_requirements_count}
              </p>
            </div>
            <div className="rounded-lg bg-sky-400/10 p-3">
              <ShoppingCart className="text-sky-400" size={20} />
            </div>
          </div>
        </Card>
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Stock by Category */}
        <Card>
          <h3 className="mb-4 text-lg font-semibold text-latte">Stock by Category</h3>
          {data.stock_by_category.length > 0 ? (
            <div className="space-y-3">
              {data.stock_by_category.map((cat) => (
                <Link
                  key={cat.category_id}
                  to={`/app/bevi-stoq/categories/${cat.category_id}`}
                  className="block"
                >
                  <div className="flex items-center justify-between rounded-lg bg-espresso/30 p-3 transition hover:bg-espresso/50">
                    <div>
                      <p className="font-medium text-latte">{cat.category_name}</p>
                      <p className="text-xs text-latte/50">{cat.product_count} products</p>
                    </div>
                    <p className="text-sm font-semibold text-gold">{cat.total_quantity.toLocaleString()}</p>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-center text-sm text-latte/50">No stock data yet</p>
          )}
        </Card>

        {/* Stock by Location */}
        <Card>
          <h3 className="mb-4 text-lg font-semibold text-latte">Stock by Location</h3>
          {data.stock_by_location.length > 0 ? (
            <div className="space-y-3">
              {data.stock_by_location.map((loc) => (
                <Link
                  key={loc.location_id}
                  to={`/app/bevi-stoq/locations/${loc.location_id}`}
                  className="block"
                >
                  <div className="flex items-center justify-between rounded-lg bg-espresso/30 p-3 transition hover:bg-espresso/50">
                    <div>
                      <p className="font-medium text-latte">{loc.location_name}</p>
                      <p className="text-xs text-latte/50">{loc.product_count} products</p>
                    </div>
                    <p className="text-sm font-semibold text-gold">{loc.total_quantity.toLocaleString()}</p>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-center text-sm text-latte/50">No locations yet</p>
          )}
        </Card>
      </div>

      {/* Recent Movements */}
      <Card>
        <h3 className="mb-4 text-lg font-semibold text-latte">Recent Stock Movements</h3>
        {data.recent_movements.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-caramel/15">
                <tr>
                  <th className="py-2 text-left text-latte/60">Product</th>
                  <th className="py-2 text-left text-latte/60">Location</th>
                  <th className="py-2 text-left text-latte/60">Type</th>
                  <th className="py-2 text-right text-latte/60">Quantity</th>
                  <th className="py-2 text-left text-latte/60">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-caramel/10">
                {data.recent_movements.map((mov) => (
                  <tr key={mov.id} className="hover:bg-espresso/20">
                    <td className="py-3 text-latte">{mov.product_name}</td>
                    <td className="py-3 text-latte/70">{mov.location_name}</td>
                    <td className="py-3">
                      <span className="rounded-full bg-caramel/20 px-2.5 py-0.5 text-xs font-medium text-caramel">
                        {mov.movement_type}
                      </span>
                    </td>
                    <td className="py-3 text-right font-medium text-latte">
                      {mov.quantity} {mov.unit}
                    </td>
                    <td className="py-3 text-xs text-latte/50">
                      {new Date(mov.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-center text-sm text-latte/50">No movements yet</p>
        )}
        <div className="mt-4 text-center">
          <Link to="/app/bevi-stoq/history">
            <Button variant="ghost">View Full History</Button>
          </Link>
        </div>
      </Card>
    </div>
  )
}
