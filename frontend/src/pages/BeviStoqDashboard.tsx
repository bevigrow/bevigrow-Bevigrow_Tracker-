import { AlertCircle, ChevronLeft, X } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api } from '../lib/api'
import { EmptyState, Spinner } from '../components/ui'

interface DashboardData {
  summary: {
    total_products: number
    out_of_stock_count: number
    total_locations: number
    total_categories: number
  }
  out_of_stock_products: Array<{
    product_id: number
    product_name: string
    status: string
    current_stock: number
    threshold: number | null
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

interface Category {
  id: number
  name: string
}

interface Product {
  id: number
  name: string
  category_id: number | null
  default_unit: string
  active: boolean
}

interface InventoryItem {
  id: number
  product_id: number
  physical_stock: number
  reserved_stock: number
}

export function BeviStoqDashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [categories, setCategories] = useState<Category[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [inventory, setInventory] = useState<InventoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedMovement, setExpandedMovement] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null)
  const [selectedProduct, setSelectedProduct] = useState<number | null>(null)

  useEffect(() => {
    fetchDashboard()
  }, [])

  const fetchDashboard = async () => {
    setLoading(true)
    setError(null)
    try {
      console.log('Fetching dashboard data...')
      const dashboardRes = await api.get<DashboardData>('/api/bevi-stoq/dashboard')
      console.log('Dashboard data loaded:', dashboardRes)
      setData(dashboardRes)

      const categoriesRes = await api.get<Category[]>('/api/bevi-stoq/categories').catch(() => [])
      console.log('Categories loaded:', categoriesRes)
      setCategories(categoriesRes || [])

      const productsRes = await api.get<Product[]>('/api/bevi-stoq/products').catch(() => [])
      console.log('Products loaded:', productsRes)
      setProducts(productsRes || [])

      const inventoryRes = await api.get<InventoryItem[]>('/api/bevi-stoq/inventory').catch(() => [])
      console.log('Inventory loaded:', inventoryRes)
      setInventory(inventoryRes || [])
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to load dashboard'
      console.error('Dashboard fetch error:', err)
      setError(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  const getTotalStockForProduct = (productId: number): number => {
    return inventory
      .filter((inv) => inv.product_id === productId)
      .reduce((sum, inv) => sum + (inv.physical_stock - inv.reserved_stock), 0)
  }

  const getProductsForCategory = (categoryId: number): Product[] => {
    return products.filter((p) => p.category_id === categoryId && p.active)
  }

  const getCategoryName = (categoryId: number): string => {
    return categories.find((c) => c.id === categoryId)?.name || 'Unknown'
  }

  const getProductName = (productId: number): string => {
    return products.find((p) => p.id === productId)?.name || 'Unknown'
  }

  if (loading) return <Spinner label="Loading inventory dashboard…" />
  if (error) return <EmptyState emoji="⚠️" title="Error" hint={error} />
  if (!data) return <EmptyState emoji="📦" title="No data" hint="Start by adding products and stock" />

  const categoryProductCounts = categories.map((cat) => ({
    id: cat.id,
    name: cat.name,
    count: getProductsForCategory(cat.id).length,
  }))

  const maxCount = Math.max(...categoryProductCounts.map((c) => c.count), 1)

  const selectedCategoryData = selectedCategory
    ? {
        id: selectedCategory,
        name: getCategoryName(selectedCategory),
        products: getProductsForCategory(selectedCategory),
      }
    : null

  const selectedProductData = selectedProduct
    ? products.find((p) => p.id === selectedProduct)
    : null

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-latte">Inventory Dashboard</h1>
        <p className="mt-1 text-sm text-latte/60">Real-time stock levels and alerts</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
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
          label="Out of Stock"
          value={data.summary.out_of_stock_count}
          icon="🚨"
          color="bg-red-500/10 text-red-400"
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Category Chart */}
        <div className="lg:col-span-2">
          {!selectedCategoryData && !selectedProductData ? (
            <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-6">
              <h2 className="mb-4 font-semibold text-latte">Products by Category</h2>
              {categoryProductCounts.length === 0 ? (
                <p className="text-sm text-latte/60">No categories with products</p>
              ) : (
                <div className="space-y-3">
                  {categoryProductCounts.map((cat) => (
                    <button
                      key={cat.id}
                      onClick={() => setSelectedCategory(cat.id)}
                      className="group w-full cursor-pointer text-left"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="min-w-24 truncate text-sm text-latte group-hover:text-gold">
                          {cat.name}
                        </span>
                        <div className="flex-1">
                          <div className="h-6 rounded bg-espresso/50 overflow-hidden">
                            <div
                              className="h-full bg-gradient-to-r from-gold/40 to-gold/20 transition-all group-hover:from-gold/60 group-hover:to-gold/40"
                              style={{ width: `${(cat.count / maxCount) * 100}%` }}
                            />
                          </div>
                        </div>
                        <span className="min-w-8 text-right text-sm font-medium text-gold">{cat.count}</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : selectedCategoryData && !selectedProductData ? (
            <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-6">
              <div className="mb-4 flex items-center gap-2">
                <button
                  onClick={() => setSelectedCategory(null)}
                  className="rounded hover:bg-caramel/20 p-1 text-latte/60 hover:text-gold"
                >
                  <ChevronLeft size={18} />
                </button>
                <h2 className="font-semibold text-latte">{selectedCategoryData.name}</h2>
                <span className="text-sm text-latte/60">({selectedCategoryData.products.length})</span>
              </div>
              {selectedCategoryData.products.length === 0 ? (
                <p className="text-sm text-latte/60">No products in this category</p>
              ) : (
                <div className="space-y-2">
                  {selectedCategoryData.products.map((prod) => (
                    <button
                      key={prod.id}
                      onClick={() => setSelectedProduct(prod.id)}
                      className="w-full cursor-pointer rounded bg-bean/50 p-3 text-left hover:bg-bean/70 transition text-sm"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <p className="font-medium text-latte">{prod.name}</p>
                          <p className="text-xs text-latte/60 mt-1">
                            {getTotalStockForProduct(prod.id).toFixed(2)} {prod.default_unit}
                          </p>
                        </div>
                        <span className="text-xs text-latte/60">→</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : selectedProductData ? (
            <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-6">
              <div className="mb-4 flex items-center gap-2">
                <button
                  onClick={() => setSelectedProduct(null)}
                  className="rounded hover:bg-caramel/20 p-1 text-latte/60 hover:text-gold"
                >
                  <ChevronLeft size={18} />
                </button>
                <h2 className="font-semibold text-latte">Product Details</h2>
              </div>
              <div className="space-y-3 text-sm">
                <div>
                  <p className="text-latte/60">Product Name</p>
                  <p className="font-medium text-latte">{selectedProductData.name}</p>
                </div>
                <div>
                  <p className="text-latte/60">Category</p>
                  <p className="font-medium text-latte">
                    {selectedProductData.category_id ? getCategoryName(selectedProductData.category_id) : 'Uncategorized'}
                  </p>
                </div>
                <div>
                  <p className="text-latte/60">Stock</p>
                  <p className="font-medium text-latte">
                    {getTotalStockForProduct(selectedProductData.id).toFixed(2)} {selectedProductData.default_unit}
                  </p>
                </div>
                <div>
                  <p className="text-latte/60">Status</p>
                  <p className={`font-medium ${getTotalStockForProduct(selectedProductData.id) > 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {getTotalStockForProduct(selectedProductData.id) > 0 ? '✓ In Stock' : '✗ Out of Stock'}
                  </p>
                </div>
              </div>
            </div>
          ) : null}
        </div>

        {/* Right Column */}
        <div className="space-y-6">
          {/* Out of Stock Panel */}
          <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
            <div className="flex items-center gap-2 mb-3">
              <AlertCircle size={16} className="text-red-400" />
              <h3 className="font-semibold text-red-400 text-sm">Out of Stock</h3>
              <span className="text-xs text-latte/60">({data.out_of_stock_products.length})</span>
            </div>
            {data.out_of_stock_products.length === 0 ? (
              <p className="text-xs text-latte/60">All products in stock</p>
            ) : (
              <div className="space-y-1">
                {data.out_of_stock_products.slice(0, 5).map((product) => (
                  <div key={product.product_id} className="text-xs text-latte/70 truncate">
                    • {product.product_name}
                  </div>
                ))}
                {data.out_of_stock_products.length > 5 && (
                  <p className="text-xs text-latte/60 mt-2">+{data.out_of_stock_products.length - 5} more</p>
                )}
              </div>
            )}
          </div>

          {/* Sticky Note - Recent Movements */}
          <div
            className={`rounded-lg border border-caramel/15 bg-espresso/40 p-4 cursor-pointer transition-all hover:border-gold/30 ${
              expandedMovement ? 'ring-1 ring-gold/20' : ''
            }`}
            onClick={() => setExpandedMovement(!expandedMovement)}
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-latte text-sm">📌 Recent Stock</h3>
              {expandedMovement && (
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setExpandedMovement(false)
                  }}
                  className="text-latte/60 hover:text-latte"
                >
                  <X size={14} />
                </button>
              )}
            </div>

            {expandedMovement ? (
              <div className="space-y-2">
                {data.recent_movements.length === 0 ? (
                  <p className="text-xs text-latte/60">No recent movements</p>
                ) : (
                  data.recent_movements.slice(0, 3).map((movement) => (
                    <div key={movement.id} className="text-xs border-t border-caramel/10 pt-2">
                      <p className="font-medium text-gold">{movement.movement_type.toUpperCase()}</p>
                      <p className="text-latte/70 text-xs mt-0.5">
                        {new Date(movement.created_at).toLocaleDateString()}
                      </p>
                      <p className="text-latte/60 text-xs mt-0.5">
                        Product: {getProductName(movement.product_id)}
                      </p>
                      <p className="text-latte/60 text-xs">
                        {movement.quantity} {movement.unit || 'units'}
                      </p>
                    </div>
                  ))
                )}
              </div>
            ) : (
              <div className="text-xs text-latte/60">
                {data.recent_movements.length === 0 ? (
                  <p>No recent movements</p>
                ) : (
                  <>
                    <p className="font-medium text-gold">{data.recent_movements[0].movement_type.toUpperCase()}</p>
                    <p className="mt-1">{new Date(data.recent_movements[0].created_at).toLocaleDateString()}</p>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
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
