import { Check, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { request } from '../../lib/api'
import { Button, Card, Input, Field, Modal, Select, Spinner, EmptyState, cx } from '../../components/ui'

interface Requirement {
  id: number
  customer_id?: number
  customer_name: string
  status: 'pending' | 'available' | 'partially_available' | 'reserved' | 'fulfilled' | 'cancelled'
  created_at: string
  items: RequirementItem[]
}

interface RequirementItem {
  id: number
  product_id: number
  quantity_required: number
  quantity_reserved: number
  quantity_fulfilled: number
  unit: string
}

interface Product {
  id: number
  name: string
}

export function BeviStoqRequirements() {
  const [requirements, setRequirements] = useState<Requirement[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [isCreating, setIsCreating] = useState(false)

  const [formData, setFormData] = useState({
    customer_name: '',
    items: [] as Array<{ product_id: string; quantity: string; unit: string }>
  })

  useEffect(() => {
    load()
  }, [])

  const load = async () => {
    try {
      setLoading(true)
      const reqs = await request<Requirement[]>('/api/bevi-stoq/requirements?limit=1000')
      const prods = await request<Product[]>('/api/bevi-stoq/products?active_only=true&limit=1000')
      setRequirements(reqs)
      setProducts(prods)
    } catch (error) {
      console.error('Load error:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async () => {
    try {
      if (formData.items.length === 0) {
        alert('Add at least one product')
        return
      }

      const payload = {
        customer_name: formData.customer_name,
        items: formData.items.map(item => ({
          product_id: parseInt(item.product_id),
          quantity_required: parseFloat(item.quantity),
          unit: item.unit
        }))
      }

      await request('/api/bevi-stoq/requirements', {
        method: 'POST',
        body: JSON.stringify(payload)
      })

      setFormData({ customer_name: '', items: [] })
      setIsCreating(false)
      load()
    } catch (error) {
      console.error('Error:', error)
    }
  }

  const handleReserve = async (id: number) => {
    try {
      await request(`/api/bevi-stoq/requirements/${id}/reserve`, { method: 'POST', body: '{}' })
      load()
    } catch (error) {
      console.error('Reserve error:', error)
    }
  }

  const handleFulfill = async (id: number) => {
    try {
      await request(`/api/bevi-stoq/requirements/${id}/fulfill`, { method: 'POST', body: '{}' })
      load()
    } catch (error) {
      console.error('Fulfill error:', error)
    }
  }

  const handleCancel = async (id: number) => {
    try {
      await request(`/api/bevi-stoq/requirements/${id}/cancel`, { method: 'POST', body: '{}' })
      load()
    } catch (error) {
      console.error('Cancel error:', error)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'available':
        return 'bg-green-500/20 text-green-300'
      case 'partially_available':
        return 'bg-orange-500/20 text-orange-300'
      case 'shortage':
        return 'bg-red-500/20 text-red-300'
      case 'fulfilled':
        return 'bg-blue-500/20 text-blue-300'
      case 'cancelled':
        return 'bg-gray-500/20 text-gray-300'
      default:
        return 'bg-yellow-500/20 text-yellow-300'
    }
  }

  if (loading) return <Spinner label="Loading requirements..." />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-3xl text-latte">Customer Requirements</h1>
        <Button onClick={() => setIsCreating(true)}>+ New Requirement</Button>
      </div>

      {requirements.length > 0 ? (
        <div className="space-y-4">
          {requirements.map((req) => (
            <Card key={req.id} className="flex flex-col">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="font-semibold text-latte">{req.customer_name}</h3>
                  <p className="text-xs text-latte/50">Created: {new Date(req.created_at).toLocaleDateString()}</p>
                </div>
                <span className={cx('rounded-full px-3 py-1 text-xs font-medium', getStatusColor(req.status))}>
                  {req.status.toUpperCase().replace(/_/g, ' ')}
                </span>
              </div>

              <div className="border-t border-caramel/15 pt-3 pb-3">
                <p className="text-sm font-medium text-latte/80 mb-2">Items:</p>
                <div className="space-y-2">
                  {req.items.map((item) => (
                    <div key={item.id} className="text-sm text-latte/70 flex justify-between">
                      <span>Product #{item.product_id}</span>
                      <span>
                        {item.quantity_required} {item.unit}
                        {item.quantity_reserved > 0 && ` (Reserved: ${item.quantity_reserved})`}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex gap-2 border-t border-caramel/15 pt-4 mt-4">
                {req.status === 'pending' && (
                  <Button variant="ghost" onClick={() => handleReserve(req.id)} className="flex-1">
                    <Check size={14} /> Reserve
                  </Button>
                )}
                {req.status === 'reserved' && (
                  <Button onClick={() => handleFulfill(req.id)} className="flex-1">
                    <Check size={14} /> Fulfill
                  </Button>
                )}
                {req.status !== 'fulfilled' && req.status !== 'cancelled' && (
                  <Button variant="danger" onClick={() => handleCancel(req.id)} className="flex-1">
                    <X size={14} /> Cancel
                  </Button>
                )}
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState
          title="No requirements yet"
          hint="Create customer requirements to reserve stock"
          action={<Button onClick={() => setIsCreating(true)}>+ New Requirement</Button>}
        />
      )}

      <Modal
        open={isCreating}
        onClose={() => {
          setIsCreating(false)
          setFormData({ customer_name: '', items: [] })
        }}
        title="New Customer Requirement"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault()
            handleCreate()
          }}
          className="space-y-4"
        >
          <Field label="Customer Name *">
            <Input
              value={formData.customer_name}
              onChange={(e) => setFormData({ ...formData, customer_name: e.target.value })}
              placeholder="e.g. ABC Foods"
              required
            />
          </Field>

          <Field label="Required Products">
            <div className="space-y-3">
              {formData.items.map((item, idx) => (
                <div key={idx} className="flex gap-2">
                  <Select
                    value={item.product_id}
                    onChange={(e) => {
                      const newItems = [...formData.items]
                      newItems[idx].product_id = e.target.value
                      setFormData({ ...formData, items: newItems })
                    }}
                    options={products.map(p => ({ value: p.id.toString(), label: p.name }))}
                  />
                  <Input
                    type="number"
                    placeholder="Qty"
                    value={item.quantity}
                    onChange={(e) => {
                      const newItems = [...formData.items]
                      newItems[idx].quantity = e.target.value
                      setFormData({ ...formData, items: newItems })
                    }}
                  />
                  <Select
                    value={item.unit}
                    onChange={(e) => {
                      const newItems = [...formData.items]
                      newItems[idx].unit = e.target.value
                      setFormData({ ...formData, items: newItems })
                    }}
                    options={[
                      { value: 'kg', label: 'kg' },
                      { value: 'g', label: 'g' },
                      { value: 'pcs', label: 'pcs' }
                    ]}
                  />
                  <Button
                    variant="danger"
                    onClick={() => {
                      const newItems = formData.items.filter((_, i) => i !== idx)
                      setFormData({ ...formData, items: newItems })
                    }}
                  >
                    Remove
                  </Button>
                </div>
              ))}
              <Button
                variant="ghost"
                onClick={() => {
                  setFormData({
                    ...formData,
                    items: [...formData.items, { product_id: '', quantity: '', unit: 'kg' }]
                  })
                }}
              >
                + Add Product
              </Button>
            </div>
          </Field>

          <div className="flex gap-3">
            <Button variant="ghost" onClick={() => setIsCreating(false)} type="button">
              Cancel
            </Button>
            <Button type="submit" className="flex-1">
              Create Requirement
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
