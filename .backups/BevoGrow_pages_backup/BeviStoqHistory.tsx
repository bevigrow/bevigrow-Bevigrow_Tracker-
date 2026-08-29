import { useEffect, useState } from 'react'
import { request } from '../../lib/api'
import { Button, Card, Input, Field, Select, Spinner, EmptyState, cx } from '../../components/ui'

interface Movement {
  id: number
  product_name: string
  location_name: string
  movement_type: string
  quantity: number
  unit: string
  reference_id?: number
  notes?: string
  created_at: string
  created_by_name?: string
}

export function BeviStoqHistory() {
  const [movements, setMovements] = useState<Movement[]>([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({
    movement_type: '',
    date_from: '',
    date_to: '',
    search: ''
  })

  useEffect(() => {
    load()
  }, [filters])

  const load = async () => {
    try {
      setLoading(true)
      const params = new URLSearchParams()

      if (filters.movement_type) params.set('movement_type', filters.movement_type)
      if (filters.date_from) params.set('date_from', filters.date_from)
      if (filters.date_to) params.set('date_to', filters.date_to)
      if (filters.search) params.set('search', filters.search)
      params.set('limit', '500')

      const data = await request<Movement[]>(`/api/bevi-stoq/stock-movements?${params}`)
      setMovements(data)
    } catch (error) {
      console.error('Load error:', error)
    } finally {
      setLoading(false)
    }
  }

  const getMovementColor = (type: string) => {
    switch (type) {
      case 'ADD':
        return 'bg-green-500/20 text-green-300'
      case 'TRANSFER':
        return 'bg-blue-500/20 text-blue-300'
      case 'RESERVE':
        return 'bg-orange-500/20 text-orange-300'
      case 'FULFILL':
        return 'bg-sky-500/20 text-sky-300'
      case 'RETURN':
        return 'bg-purple-500/20 text-purple-300'
      default:
        return 'bg-gray-500/20 text-gray-300'
    }
  }

  const handleReset = () => {
    setFilters({ movement_type: '', date_from: '', date_to: '', search: '' })
  }

  if (loading) return <Spinner label="Loading stock history..." />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-3xl text-latte">Stock History</h1>
      </div>

      {/* Filters */}
      <Card>
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <Field label="Movement Type">
              <Select
                value={filters.movement_type}
                onChange={(e) => setFilters({ ...filters, movement_type: e.target.value })}
                options={[
                  { value: '', label: 'All Types' },
                  { value: 'ADD', label: 'Add Stock' },
                  { value: 'TRANSFER', label: 'Transfer' },
                  { value: 'RESERVE', label: 'Reserve' },
                  { value: 'FULFILL', label: 'Fulfill' },
                  { value: 'RETURN', label: 'Return' }
                ]}
              />
            </Field>

            <Field label="From Date">
              <Input
                type="date"
                value={filters.date_from}
                onChange={(e) => setFilters({ ...filters, date_from: e.target.value })}
              />
            </Field>

            <Field label="To Date">
              <Input
                type="date"
                value={filters.date_to}
                onChange={(e) => setFilters({ ...filters, date_to: e.target.value })}
              />
            </Field>

            <Field label="Search">
              <Input
                placeholder="Product, location..."
                value={filters.search}
                onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              />
            </Field>

            <div className="flex items-end gap-2">
              <Button variant="ghost" onClick={handleReset} className="flex-1">
                Reset
              </Button>
            </div>
          </div>
        </div>
      </Card>

      {/* Movements Table */}
      {movements.length > 0 ? (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-caramel/15">
                <tr>
                  <th className="py-3 text-left text-latte/60">Date</th>
                  <th className="py-3 text-left text-latte/60">Product</th>
                  <th className="py-3 text-left text-latte/60">Location</th>
                  <th className="py-3 text-left text-latte/60">Type</th>
                  <th className="py-3 text-right text-latte/60">Quantity</th>
                  <th className="py-3 text-left text-latte/60">By</th>
                  <th className="py-3 text-left text-latte/60">Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-caramel/10">
                {movements.map((mov) => (
                  <tr key={mov.id} className="hover:bg-espresso/20">
                    <td className="py-3 text-latte/70">
                      {new Date(mov.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 text-latte font-medium">{mov.product_name}</td>
                    <td className="py-3 text-latte/70">{mov.location_name}</td>
                    <td className="py-3">
                      <span className={cx('rounded-full px-2.5 py-0.5 text-xs font-medium', getMovementColor(mov.movement_type))}>
                        {mov.movement_type}
                      </span>
                    </td>
                    <td className="py-3 text-right font-medium text-latte">
                      {mov.quantity} {mov.unit}
                    </td>
                    <td className="py-3 text-xs text-latte/50">{mov.created_by_name || 'System'}</td>
                    <td className="max-w-sm py-3 text-xs text-latte/50">{mov.notes || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        <EmptyState
          title="No movements yet"
          hint={filters.search || filters.movement_type ? 'Try adjusting your filters' : 'Stock movements will appear here'}
        />
      )}

      {/* Summary Stats */}
      {movements.length > 0 && (
        <Card>
          <h3 className="mb-4 text-lg font-semibold text-latte">Summary</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <div>
              <p className="text-xs text-latte/60">Total Movements</p>
              <p className="mt-1 text-2xl font-bold text-gold">{movements.length}</p>
            </div>
            {['ADD', 'TRANSFER', 'RESERVE', 'FULFILL', 'RETURN'].map((type) => {
              const count = movements.filter(m => m.movement_type === type).length
              return count > 0 ? (
                <div key={type}>
                  <p className="text-xs text-latte/60">{type}</p>
                  <p className="mt-1 text-2xl font-bold text-latte">{count}</p>
                </div>
              ) : null
            })}
          </div>
        </Card>
      )}
    </div>
  )
}
