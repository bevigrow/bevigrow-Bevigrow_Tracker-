import { useState } from 'react'
import { request } from '../../lib/api'
import { Button, Card, Input, Field, Modal, Select } from '../../components/ui'

export function BeviStoqStock() {
  const [isAdding, setIsAdding] = useState(false)
  const [formData, setFormData] = useState({
    product_id: '',
    location_id: '',
    quantity: '',
    unit: 'kg',
    reference: '',
    notes: ''
  })

  const handleAddStock = async () => {
    try {
      await request('/api/bevi-stoq/stock/add', {
        method: 'POST',
        body: JSON.stringify({
          product_id: parseInt(formData.product_id),
          location_id: parseInt(formData.location_id),
          quantity: parseFloat(formData.quantity),
          unit: formData.unit,
          reference: formData.reference || undefined,
          notes: formData.notes || undefined
        })
      })
      setFormData({ product_id: '', location_id: '', quantity: '', unit: 'kg', reference: '', notes: '' })
      setIsAdding(false)
    } catch (error) {
      console.error('Error adding stock:', error)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-3xl text-latte">Stock Management</h1>
        <Button onClick={() => setIsAdding(true)}>+ Add Stock</Button>
      </div>

      <Card>
        <p className="text-center text-latte/60">Stock management interface - Add stock, transfer between locations, view inventory levels</p>
      </Card>

      <Modal
        open={isAdding}
        onClose={() => setIsAdding(false)}
        title="Add Stock"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault()
            handleAddStock()
          }}
          className="space-y-4"
        >
          <Field label="Product *">
            <Input placeholder="Select product" required />
          </Field>

          <Field label="Location *">
            <Input placeholder="Select location" required />
          </Field>

          <Field label="Quantity *">
            <Input type="number" placeholder="0" required />
          </Field>

          <Field label="Unit *">
            <Select
              value={formData.unit}
              onChange={(e) => setFormData({ ...formData, unit: e.target.value })}
              options={[
                { value: 'kg', label: 'kg' },
                { value: 'g', label: 'g' },
                { value: 'pcs', label: 'pcs' }
              ]}
            />
          </Field>

          <Field label="Notes">
            <Input placeholder="Optional notes" />
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
      </Modal>
    </div>
  )
}
