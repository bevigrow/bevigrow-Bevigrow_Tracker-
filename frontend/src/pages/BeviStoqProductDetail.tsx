import { ArrowLeft, Edit2, Trash2, Plus } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { api } from '../lib/api'
import { EmptyState, Spinner } from '../components/ui'
import { useToast } from '../lib/toast'

interface Product {
  id: number
  name: string
  category_id: number | null
  default_unit: string
  alert_quantity: number | null
  notes: string | null
  active: boolean
  created_at: string
}

interface InventoryItem {
  id: number
  product_id: number
  location_id: number
  physical_stock: number
  reserved_stock: number
}

interface Location {
  id: number
  name: string
}

interface Category {
  id: number
  name: string
}

interface StockMovement {
  id: number
  product_id: number
  movement_type: string
  quantity: number
  unit: string | null
  created_at: string
}

export function BeviStoqProductDetail() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const toast = useToast()

  const [product, setProduct] = useState<Product | null>(null)
  const [inventory, setInventory] = useState<InventoryItem[]>([])
  const [locations, setLocations] = useState<Location[]>([])
  const [category, setCategory] = useState<Category | null>(null)
  const [movements, setMovements] = useState<StockMovement[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchData()
  }, [id])

  const fetchData = async () => {
    try {
      if (!id) return
      const productId = parseInt(id)

      const [prodRes, invRes, locRes, movRes] = await Promise.all([
        api.get<Product>(`/api/bevi-stoq/products/${productId}`),
        api.get<InventoryItem[]>('/api/bevi-stoq/inventory'),
        api.get<Location[]>('/api/bevi-stoq/locations'),
        api.get<StockMovement[]>(`/api/bevi-stoq/stock-movements?product_id=${productId}`),
      ])

      setProduct(prodRes)
      setLocations(locRes)
      setMovements(movRes)

      // Filter inventory for this product
      const productInventory = invRes.filter((inv) => inv.product_id === productId)
      setInventory(productInventory)

      // Fetch category if exists
      if (prodRes.category_id) {
        try {
          const catRes = await api.get<Category>(`/api/bevi-stoq/categories/${prodRes.category_id}`)
          setCategory(catRes)
        } catch {
          // Category not found or error
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load product details')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async () => {
    if (!product || !confirm('Delete this product?')) return
    try {
      await api.delete(`/api/bevi-stoq/products/${product.id}`)
      toast.success('Product deleted successfully')
      navigate('/app/bevi-stoq/products')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete product')
    }
  }

  const getLocationName = (locationId: number) => {
    return locations.find((l) => l.id === locationId)?.name || `Location ${locationId}`
  }

  const getTotalStock = () => {
    return inventory.reduce((total, inv) => total + (inv.physical_stock - inv.reserved_stock), 0)
  }

  if (loading) return <Spinner label="Loading product details…" />
  if (error) return <EmptyState emoji="⚠️" title="Error" hint={error} />
  if (!product) return <EmptyState emoji="📦" title="Product not found" hint="This product does not exist" />

  const totalStock = getTotalStock()

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/app/bevi-stoq/products')}
            className="rounded p-2 hover:bg-caramel/20 text-latte/60 hover:text-gold"
          >
            <ArrowLeft size={20} />
          </button>
          <div>
            <h1 className="text-3xl font-bold text-latte">{product.name}</h1>
            {category && <p className="mt-1 text-sm text-latte/60">Category: {category.name}</p>}
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => navigate(`/app/bevi-stoq/products/${product.id}/edit`)}
            className="rounded p-2 hover:bg-caramel/20 text-latte/60 hover:text-gold"
          >
            <Edit2 size={20} />
          </button>
          <button
            onClick={handleDelete}
            className="rounded p-2 hover:bg-caramel/20 text-latte/60 hover:text-red-400"
          >
            <Trash2 size={20} />
          </button>
        </div>
      </div>

      {/* Product Info Cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
          <p className="text-xs uppercase tracking-wide text-latte/60">Total Stock</p>
          <p className={`mt-2 text-2xl font-bold ${totalStock > 0 ? 'text-green-400' : 'text-red-400'}`}>
            {totalStock.toFixed(2)}
          </p>
          <p className="text-xs text-latte/50 mt-1">{product.default_unit}</p>
        </div>

        <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
          <p className="text-xs uppercase tracking-wide text-latte/60">Locations</p>
          <p className="mt-2 text-2xl font-bold text-gold">{inventory.length}</p>
        </div>

        <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
          <p className="text-xs uppercase tracking-wide text-latte/60">Unit</p>
          <p className="mt-2 text-2xl font-bold text-latte">{product.default_unit}</p>
        </div>

        <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
          <p className="text-xs uppercase tracking-wide text-latte/60">Status</p>
          <p className="mt-2 text-2xl font-bold text-latte">{product.active ? '✓ Active' : '✗ Inactive'}</p>
        </div>
      </div>

      {/* Notes */}
      {product.notes && (
        <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
          <p className="text-sm font-medium text-latte/70">Notes</p>
          <p className="mt-2 text-sm text-latte">{product.notes}</p>
        </div>
      )}

      {/* Inventory by Location */}
      <div>
        <h2 className="text-xl font-bold text-latte mb-4">Inventory by Location</h2>
        {inventory.length === 0 ? (
          <EmptyState emoji="📍" title="No inventory" hint="No stock at any location" />
        ) : (
          <div className="grid grid-cols-1 gap-3">
            {inventory.map((inv) => {
              const available = inv.physical_stock - inv.reserved_stock
              return (
                <div key={inv.id} className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-semibold text-latte">{getLocationName(inv.location_id)}</p>
                      <p className="text-sm text-latte/60 mt-1">
                        Physical: {inv.physical_stock.toFixed(2)} | Reserved: {inv.reserved_stock.toFixed(2)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className={`text-2xl font-bold ${available > 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {available.toFixed(2)}
                      </p>
                      <p className="text-xs text-latte/50">Available</p>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Recent Movements */}
      <div>
        <h2 className="text-xl font-bold text-latte mb-4">Recent Stock Movements</h2>
        {movements.length === 0 ? (
          <EmptyState emoji="📊" title="No movements" hint="No stock movements yet" />
        ) : (
          <div className="space-y-2">
            {movements.slice(0, 10).map((mov) => (
              <div key={mov.id} className="rounded-lg border border-caramel/15 bg-espresso/40 p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-semibold text-latte text-sm">{mov.movement_type.toUpperCase().replace(/_/g, ' ')}</p>
                    <p className="text-xs text-latte/50 mt-1">{new Date(mov.created_at).toLocaleDateString()}</p>
                  </div>
                  <p className="text-sm font-medium text-gold">
                    {mov.quantity} {mov.unit || product.default_unit}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
