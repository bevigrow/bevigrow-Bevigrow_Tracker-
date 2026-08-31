import { ChevronRight, Package } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../lib/api'
import { EmptyState, Spinner } from '../components/ui'

interface Product {
  id: number
  name: string
  category_id: number | null
  default_unit: string
  active: boolean
}

interface Category {
  id: number
  name: string
}

interface InventoryItem {
  id: number
  product_id: number
  location_id: number
  physical_stock: number
  reserved_stock: number
}

export function BeviStoqProductsByCategory() {
  const navigate = useNavigate()
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [inventory, setInventory] = useState<InventoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const [prodRes, catRes, invRes] = await Promise.all([
        api.get<Product[]>('/api/bevi-stoq/products'),
        api.get<Category[]>('/api/bevi-stoq/categories'),
        api.get<InventoryItem[]>('/api/bevi-stoq/inventory'),
      ])
      setProducts(prodRes)
      setCategories(catRes)
      setInventory(invRes)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load products')
    } finally {
      setLoading(false)
    }
  }

  const getTotalStock = (productId: number) => {
    return inventory
      .filter((inv) => inv.product_id === productId)
      .reduce((sum, inv) => sum + (inv.physical_stock - inv.reserved_stock), 0)
  }

  if (loading) return <Spinner label="Loading products…" />
  if (error) return <EmptyState emoji="⚠️" title="Error" hint={error} />

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-latte">Products by Category</h1>
        <p className="mt-1 text-sm text-latte/60">Browse inventory organized by category</p>
      </div>

      {/* Categories with Products */}
      <div className="space-y-4">
        {categories.map((cat) => {
          const catProducts = products.filter((p) => p.category_id === cat.id && p.active)
          if (catProducts.length === 0) return null

          return (
            <div key={cat.id} className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
              <h2 className="font-semibold text-latte mb-3">{cat.name}</h2>
              <div className="space-y-2">
                {catProducts.map((prod) => {
                  const stock = getTotalStock(prod.id)
                  return (
                    <button
                      key={prod.id}
                      onClick={() => navigate(`/app/bevi-stoq/products`)}
                      className="w-full flex items-center justify-between rounded-lg bg-bean/50 p-3 hover:bg-bean/70 transition text-left"
                    >
                      <div className="flex-1">
                        <p className="font-medium text-latte">{prod.name}</p>
                        <p className={`text-xs mt-1 ${stock > 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {stock.toFixed(2)} {prod.default_unit}
                        </p>
                      </div>
                      <ChevronRight size={18} className="text-gold/60" />
                    </button>
                  )
                })}
              </div>
            </div>
          )
        })}

        {/* Uncategorized Products */}
        {(() => {
          const uncatProducts = products.filter((p) => !p.category_id && p.active)
          if (uncatProducts.length === 0) return null

          return (
            <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
              <h2 className="font-semibold text-latte mb-3">Uncategorized</h2>
              <div className="space-y-2">
                {uncatProducts.map((prod) => {
                  const stock = getTotalStock(prod.id)
                  return (
                    <button
                      key={prod.id}
                      onClick={() => navigate(`/app/bevi-stoq/products`)}
                      className="w-full flex items-center justify-between rounded-lg bg-bean/50 p-3 hover:bg-bean/70 transition text-left"
                    >
                      <div className="flex-1">
                        <p className="font-medium text-latte">{prod.name}</p>
                        <p className={`text-xs mt-1 ${stock > 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {stock.toFixed(2)} {prod.default_unit}
                        </p>
                      </div>
                      <ChevronRight size={18} className="text-gold/60" />
                    </button>
                  )
                })}
              </div>
            </div>
          )
        })()}

        {categories.length === 0 && products.length === 0 && (
          <EmptyState emoji="📦" title="No products" hint="Add products to get started" />
        )}
      </div>
    </div>
  )
}
