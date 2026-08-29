import { useEffect, useState } from 'react'
import { Download } from 'lucide-react'

import { api } from '../lib/api'
import { EmptyState, Spinner } from '../components/ui'

interface StockReport {
  total_products: number
  low_stock_count: number
  out_of_stock_count: number
  items: Array<{
    product_name: string
    category_name: string
    physical_stock: number
    reserved_stock: number
    available_stock: number
    unit: string
    low_stock_threshold: number
    status: string
    location: string
  }>
}

interface CategoryReport {
  category: string
  product_count: number
  total_physical_stock: number
  total_available_stock: number
}

interface LocationReport {
  location: string
  item_count: number
  total_physical_stock: number
  total_available_stock: number
}

export function BeviStoqReports() {
  const [stockReport, setStockReport] = useState<StockReport | null>(null)
  const [categoryReports, setCategoryReports] = useState<CategoryReport[]>([])
  const [locationReports, setLocationReports] = useState<LocationReport[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('stock')

  useEffect(() => {
    fetchReports()
  }, [])

  const fetchReports = async () => {
    try {
      const [stockRes, catRes, locRes] = await Promise.all([
        api.get<StockReport>('/api/bevi-stoq/reports/inventory'),
        api.get<CategoryReport[]>('/api/bevi-stoq/reports/stock-by-category'),
        api.get<LocationReport[]>('/api/bevi-stoq/reports/stock-by-location'),
      ])
      setStockReport(stockRes)
      setCategoryReports(catRes)
      setLocationReports(locRes)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load reports')
    } finally {
      setLoading(false)
    }
  }

  const exportToCSV = (data: any[], filename: string) => {
    const csv = [
      Object.keys(data[0]).join(','),
      ...data.map(row => Object.values(row).join(',')),
    ].join('\n')

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
  }

  if (loading) return <Spinner label="Loading reports…" />
  if (error) return <EmptyState emoji="⚠️" title="Error" hint={error} />

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-latte">Inventory Reports</h1>
        <p className="mt-1 text-sm text-latte/60">Detailed analytics and exports</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-4 border-b border-caramel/15">
        <button
          onClick={() => setActiveTab('stock')}
          className={`px-4 py-2 text-sm font-medium ${
            activeTab === 'stock'
              ? 'text-gold border-b-2 border-gold'
              : 'text-latte/60 hover:text-latte'
          }`}
        >
          Stock Report
        </button>
        <button
          onClick={() => setActiveTab('category')}
          className={`px-4 py-2 text-sm font-medium ${
            activeTab === 'category'
              ? 'text-gold border-b-2 border-gold'
              : 'text-latte/60 hover:text-latte'
          }`}
        >
          By Category
        </button>
        <button
          onClick={() => setActiveTab('location')}
          className={`px-4 py-2 text-sm font-medium ${
            activeTab === 'location'
              ? 'text-gold border-b-2 border-gold'
              : 'text-latte/60 hover:text-latte'
          }`}
        >
          By Location
        </button>
      </div>

      {/* Stock Report Tab */}
      {activeTab === 'stock' && stockReport && (
        <div className="space-y-4">
          {/* Summary */}
          <div className="grid grid-cols-4 gap-4">
            <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
              <p className="text-xs uppercase tracking-wide text-latte/60">Total Products</p>
              <p className="mt-1 text-2xl font-bold text-latte">{stockReport.total_products}</p>
            </div>
            <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
              <p className="text-xs uppercase tracking-wide text-latte/60">Normal Stock</p>
              <p className="mt-1 text-2xl font-bold text-green-400">
                {stockReport.total_products - stockReport.low_stock_count - stockReport.out_of_stock_count}
              </p>
            </div>
            <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
              <p className="text-xs uppercase tracking-wide text-yellow-400">Low Stock</p>
              <p className="mt-1 text-2xl font-bold text-yellow-400">{stockReport.low_stock_count}</p>
            </div>
            <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
              <p className="text-xs uppercase tracking-wide text-red-400">Out of Stock</p>
              <p className="mt-1 text-2xl font-bold text-red-400">{stockReport.out_of_stock_count}</p>
            </div>
          </div>

          {/* Export Button */}
          <button
            onClick={() => exportToCSV(stockReport.items, 'stock-report.csv')}
            className="flex items-center gap-2 rounded bg-gold/20 px-4 py-2 text-sm font-medium text-gold hover:bg-gold/30"
          >
            <Download size={16} />
            Export to CSV
          </button>

          {/* Table */}
          <div className="overflow-x-auto rounded-lg border border-caramel/15">
            <table className="w-full">
              <thead>
                <tr className="border-b border-caramel/15 bg-espresso/60">
                  <th className="px-4 py-3 text-left text-sm font-semibold text-latte">Product</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-latte">Category</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-latte">Location</th>
                  <th className="px-4 py-3 text-right text-sm font-semibold text-latte">Physical</th>
                  <th className="px-4 py-3 text-right text-sm font-semibold text-latte">Reserved</th>
                  <th className="px-4 py-3 text-right text-sm font-semibold text-latte">Available</th>
                  <th className="px-4 py-3 text-center text-sm font-semibold text-latte">Status</th>
                </tr>
              </thead>
              <tbody>
                {stockReport.items.map((item, idx) => (
                  <tr key={idx} className="border-b border-caramel/15 hover:bg-espresso/40">
                    <td className="px-4 py-3 text-sm text-latte">{item.product_name}</td>
                    <td className="px-4 py-3 text-sm text-latte/70">{item.category_name}</td>
                    <td className="px-4 py-3 text-sm text-latte/70">{item.location}</td>
                    <td className="px-4 py-3 text-right text-sm text-latte">
                      {item.physical_stock} {item.unit}
                    </td>
                    <td className="px-4 py-3 text-right text-sm text-latte/70">
                      {item.reserved_stock} {item.unit}
                    </td>
                    <td className="px-4 py-3 text-right text-sm font-medium text-gold">
                      {item.available_stock} {item.unit}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span
                        className={`inline-block rounded px-2 py-1 text-xs font-medium ${
                          item.status === 'OUT_OF_STOCK'
                            ? 'bg-red-500/20 text-red-400'
                            : item.status === 'LOW_STOCK'
                            ? 'bg-yellow-500/20 text-yellow-400'
                            : 'bg-green-500/20 text-green-400'
                        }`}
                      >
                        {item.status.replace('_', ' ')}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Category Report Tab */}
      {activeTab === 'category' && (
        <div className="space-y-4">
          <button
            onClick={() => exportToCSV(categoryReports, 'category-report.csv')}
            className="flex items-center gap-2 rounded bg-gold/20 px-4 py-2 text-sm font-medium text-gold hover:bg-gold/30"
          >
            <Download size={16} />
            Export to CSV
          </button>

          <div className="grid gap-4 sm:grid-cols-2">
            {categoryReports.map((cat, idx) => (
              <div key={idx} className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
                <h3 className="font-semibold text-latte mb-3">{cat.category}</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-latte/60">Products:</span>
                    <span className="text-latte">{cat.product_count}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-latte/60">Physical Stock:</span>
                    <span className="text-latte">{cat.total_physical_stock}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-latte/60">Available:</span>
                    <span className="text-gold font-medium">{cat.total_available_stock}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Location Report Tab */}
      {activeTab === 'location' && (
        <div className="space-y-4">
          <button
            onClick={() => exportToCSV(locationReports, 'location-report.csv')}
            className="flex items-center gap-2 rounded bg-gold/20 px-4 py-2 text-sm font-medium text-gold hover:bg-gold/30"
          >
            <Download size={16} />
            Export to CSV
          </button>

          <div className="grid gap-4 sm:grid-cols-2">
            {locationReports.map((loc, idx) => (
              <div key={idx} className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
                <h3 className="font-semibold text-latte mb-3">{loc.location}</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-latte/60">Items:</span>
                    <span className="text-latte">{loc.item_count}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-latte/60">Physical Stock:</span>
                    <span className="text-latte">{loc.total_physical_stock}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-latte/60">Available:</span>
                    <span className="text-gold font-medium">{loc.total_available_stock}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
