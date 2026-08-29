import { useEffect, useState } from 'react'
import { request } from '../../lib/api'
import { Button, Card, Input, Field, Modal, Select, Spinner, cx } from '../../components/ui'

interface Product {
  id: number
  name: string
  default_unit: string
}

interface Location {
  id: number
  name: string
}

export function BeviStoqStock() {
  const [products, setProducts] = useState<Product[]>([])
  const [locations, setLocations] = useState<Location[]>([])
  const [loading, setLoading] = useState(true)
  const [isAdding, setIsAdding] = useState(false)
  const [activeTab, setActiveTab] = useState<'add' | 'transfer'>('add')

  const [formData, setFormData] = useState({
    product_id: '',
    location_id: '',
    quantity: '',
    unit: 'kg',
    reference: '',
    notes: '',
    restock_date: '',
    supplier: '',
    cost_per_unit: '',
    total_cost: ''
  })
  const [error, setError] = useState<string>('')

  const [transferData, setTransferData] = useState({
    product_id: '',
    from_location_id: '',
    to_location_id: '',
    quantity: '',
    unit: 'kg',
    transfer_date: '',
    notes: ''
  })

  useEffect(() => {
    load()
  }, [])

  const load = async () => {
    try {
      setLoading(true)
      const [prods, locs] = await Promise.all([
        request<Product[]>('/api/bevi-stoq/products?active_only=true&limit=1000'),
        request<Location[]>('/api/bevi-stoq/locations?active_only=true&limit=1000')
      ])
      setProducts(prods)
      setLocations(locs)
    } catch (error) {
      console.error('Load error:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleAddStock = async () => {
    try {
      setError('')
      if (!formData.product_id || !formData.location_id || !formData.quantity) {
        setError('Fill all required fields (Product, Location, Quantity)')
        return
      }

      let refId: number | null = null
      if (formData.reference) {
        const parsed = parseInt(formData.reference, 10)
        if (isNaN(parsed)) {
          setError('Reference ID must be a valid number')
          return
        }
        refId = parsed
      }

      const payload = {
        product_id: parseInt(formData.product_id, 10),
        location_id: parseInt(formData.location_id, 10),
        quantity: parseFloat(formData.quantity),
        unit: formData.unit,
        reference_id: refId,
        notes: formData.notes,
        restock_date: formData.restock_date || null,
        supplier: formData.supplier || null,
        cost_per_unit: formData.cost_per_unit ? parseFloat(formData.cost_per_unit) : null,
        total_cost: formData.total_cost ? parseFloat(formData.total_cost) : null
      }

      await request('/api/bevi-stoq/stock/add', {
        method: 'POST',
        body: JSON.stringify(payload)
      })

      setFormData({
        product_id: '', location_id: '', quantity: '', unit: 'kg', reference: '',
        notes: '', restock_date: '', supplier: '', cost_per_unit: '', total_cost: ''
      })
      setIsAdding(false)
      load()
    } catch (error) {
      setError(`Error: ${error instanceof Error ? error.message : 'Failed to add stock'}`)
    }
  }

  const handleTransferStock = async () => {
    try {
      setError('')
      if (!transferData.product_id || !transferData.from_location_id || !transferData.to_location_id || !transferData.quantity) {
        setError('Fill all required fields (Product, From/To Location, Quantity)')
        return
      }

      if (transferData.from_location_id === transferData.to_location_id) {
        setError('From and To locations must be different')
        return
      }

      const payload = {
        product_id: parseInt(transferData.product_id, 10),
        from_location_id: parseInt(transferData.from_location_id, 10),
        to_location_id: parseInt(transferData.to_location_id, 10),
        quantity: parseFloat(transferData.quantity),
        unit: transferData.unit,
        transfer_date: transferData.transfer_date || null,
        notes: transferData.notes
      }

      await request('/api/bevi-stoq/stock-transfer', {
        method: 'POST',
        body: JSON.stringify(payload)
      })

      setTransferData({
        product_id: '', from_location_id: '', to_location_id: '', quantity: '',
        unit: 'kg', transfer_date: '', notes: ''
      })
      setIsAdding(false)
      load()
    } catch (error) {
      setError(`Error: ${error instanceof Error ? error.message : 'Failed to transfer stock'}`)
    }
  }

  if (loading) return <Spinner label="Loading..." />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-3xl text-latte">Stock Operations</h1>
        <Button onClick={() => setIsAdding(true)}>+ New Operation</Button>
      </div>

      <Card>
        <div className="flex gap-4 border-b border-caramel/15">
          <button
            onClick={() => setActiveTab('add')}
            className={cx(
              'px-4 py-3 font-medium text-sm transition',
              activeTab === 'add'
                ? 'border-b-2 border-gold text-gold'
                : 'text-latte/60 hover:text-latte'
            )}
          >
            Add Stock
          </button>
          <button
            onClick={() => setActiveTab('transfer')}
            className={cx(
              'px-4 py-3 font-medium text-sm transition',
              activeTab === 'transfer'
                ? 'border-b-2 border-gold text-gold'
                : 'text-latte/60 hover:text-latte'
            )}
          >
            Transfer Stock
          </button>
        </div>
        <div className="mt-4">
          {activeTab === 'add' ? (
            <p className="text-sm text-latte/60">Record new stock arrival with dates, supplier info, and cost tracking</p>
          ) : (
            <p className="text-sm text-latte/60">Move stock from one location to another with date tracking</p>
          )}
        </div>
      </Card>

      <Modal
        open={isAdding}
        onClose={() => {
          setIsAdding(false)
          setActiveTab('add')
          setFormData({
            product_id: '', location_id: '', quantity: '', unit: 'kg', reference: '',
            notes: '', restock_date: '', supplier: '', cost_per_unit: '', total_cost: ''
          })
          setTransferData({
            product_id: '', from_location_id: '', to_location_id: '', quantity: '',
            unit: 'kg', transfer_date: '', notes: ''
          })
        }}
        title={activeTab === 'add' ? 'Add Stock' : 'Transfer Stock'}
      >
        {activeTab === 'add' ? (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              handleAddStock()
            }}
            className="space-y-4"
          >
            {error && (
              <div className="rounded-lg bg-red-500/20 px-3 py-2 text-sm text-red-300">
                {error}
              </div>
            )}
            <Field label="Product *">
              <Select
                value={formData.product_id}
                onChange={(e) => setFormData({ ...formData, product_id: e.target.value })}
                options={products.map(p => ({ value: p.id.toString(), label: p.name }))}
                required
              />
            </Field>

            <Field label="Location *">
              <Select
                value={formData.location_id}
                onChange={(e) => setFormData({ ...formData, location_id: e.target.value })}
                options={locations.map(l => ({ value: l.id.toString(), label: l.name }))}
                required
              />
            </Field>

            <Field label="Quantity *">
              <Input
                type="number"
                placeholder="e.g. 100"
                value={formData.quantity}
                onChange={(e) => setFormData({ ...formData, quantity: e.target.value })}
                required
              />
            </Field>

            <Field label="Unit *">
              <Select
                value={formData.unit}
                onChange={(e) => setFormData({ ...formData, unit: e.target.value })}
                options={[
                  { value: 'kg', label: 'kg' },
                  { value: 'g', label: 'g' },
                  { value: 'tonne', label: 'tonne' },
                  { value: 'pcs', label: 'pcs' },
                  { value: 'litre', label: 'litre' },
                  { value: 'ml', label: 'ml' },
                  { value: 'box', label: 'box' },
                  { value: 'bag', label: 'bag' }
                ]}
              />
            </Field>

            <Field label="Restock Date">
              <Input
                type="date"
                value={formData.restock_date}
                onChange={(e) => setFormData({ ...formData, restock_date: e.target.value })}
              />
            </Field>

            <Field label="Supplier">
              <Input
                placeholder="Supplier name"
                value={formData.supplier}
                onChange={(e) => setFormData({ ...formData, supplier: e.target.value })}
              />
            </Field>

            <Field label="Cost per Unit">
              <Input
                type="number"
                placeholder="₹0.00"
                value={formData.cost_per_unit}
                onChange={(e) => setFormData({ ...formData, cost_per_unit: e.target.value })}
                step="0.01"
              />
            </Field>

            <Field label="Total Cost">
              <Input
                type="number"
                placeholder="₹0.00"
                value={formData.total_cost}
                onChange={(e) => setFormData({ ...formData, total_cost: e.target.value })}
                step="0.01"
              />
            </Field>

            <Field label="Reference (Optional)">
              <Input
                type="number"
                placeholder="Order/Invoice ID"
                value={formData.reference}
                onChange={(e) => setFormData({ ...formData, reference: e.target.value })}
              />
            </Field>

            <Field label="Notes (Optional)">
              <Input
                placeholder="Any additional info..."
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              />
            </Field>

            <div className="flex gap-3">
              <Button variant="ghost" onClick={() => setIsAdding(false)} type="button">
                Cancel
              </Button>
              <Button type="submit" className="flex-1">
                Add Stock
              </Button>
            </div>
          </form>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              handleTransferStock()
            }}
            className="space-y-4"
          >
            {error && (
              <div className="rounded-lg bg-red-500/20 px-3 py-2 text-sm text-red-300">
                {error}
              </div>
            )}
            <Field label="Product *">
              <Select
                value={transferData.product_id}
                onChange={(e) => setTransferData({ ...transferData, product_id: e.target.value })}
                options={products.map(p => ({ value: p.id.toString(), label: p.name }))}
                required
              />
            </Field>

            <Field label="From Location *">
              <Select
                value={transferData.from_location_id}
                onChange={(e) => setTransferData({ ...transferData, from_location_id: e.target.value })}
                options={locations.map(l => ({ value: l.id.toString(), label: l.name }))}
                required
              />
            </Field>

            <Field label="To Location *">
              <Select
                value={transferData.to_location_id}
                onChange={(e) => setTransferData({ ...transferData, to_location_id: e.target.value })}
                options={locations.map(l => ({ value: l.id.toString(), label: l.name }))}
                required
              />
            </Field>

            <Field label="Quantity *">
              <Input
                type="number"
                placeholder="e.g. 100"
                value={transferData.quantity}
                onChange={(e) => setTransferData({ ...transferData, quantity: e.target.value })}
                required
              />
            </Field>

            <Field label="Unit *">
              <Select
                value={transferData.unit}
                onChange={(e) => setTransferData({ ...transferData, unit: e.target.value })}
                options={[
                  { value: 'kg', label: 'kg' },
                  { value: 'g', label: 'g' },
                  { value: 'tonne', label: 'tonne' },
                  { value: 'pcs', label: 'pcs' },
                  { value: 'litre', label: 'litre' },
                  { value: 'ml', label: 'ml' },
                  { value: 'box', label: 'box' },
                  { value: 'bag', label: 'bag' }
                ]}
              />
            </Field>

            <Field label="Transfer Date">
              <Input
                type="date"
                value={transferData.transfer_date}
                onChange={(e) => setTransferData({ ...transferData, transfer_date: e.target.value })}
              />
            </Field>

            <Field label="Notes (Optional)">
              <Input
                placeholder="Any additional info..."
                value={transferData.notes}
                onChange={(e) => setTransferData({ ...transferData, notes: e.target.value })}
              />
            </Field>

            <div className="flex gap-3">
              <Button variant="ghost" onClick={() => setIsAdding(false)} type="button">
                Cancel
              </Button>
              <Button type="submit" className="flex-1">
                Transfer Stock
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  )
}
