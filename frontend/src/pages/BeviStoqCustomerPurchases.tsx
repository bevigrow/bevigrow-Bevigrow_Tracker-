import { Trash2, Edit2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { request } from '../lib/api'
import { Button, Card, Input, Field, Modal, Select, Spinner, EmptyState, ConfirmDialog, cx } from '../components/ui'

interface CustomerPurchase {
  id: number
  customer_id?: number
  customer_name: string
  product_name: string
  quantity: number
  unit: string
  purchase_date: string
  payment_status: 'paid' | 'pending' | 'overdue'
  payment_method?: string
  amount: number
  notes?: string
}

interface Product {
  id: number
  name: string
  default_unit: string
}

export function BeviStoqCustomerPurchases() {
  const [purchases, setPurchases] = useState<CustomerPurchase[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [isAdding, setIsAdding] = useState(false)
  const [paymentFilter, setPaymentFilter] = useState('')
  const [dateFilter, setDateFilter] = useState({ from: '', to: '' })

  const [formData, setFormData] = useState({
    customer_name: '',
    product_id: '',
    quantity: '',
    unit: 'kg',
    purchase_date: new Date().toISOString().split('T')[0],
    payment_status: 'pending' as 'pending' | 'paid' | 'overdue',
    payment_method: 'cash',
    amount: '',
    notes: ''
  })
  const [isEditing, setIsEditing] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [error, setError] = useState<string>('')
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)

  useEffect(() => {
    load()
  }, [paymentFilter, dateFilter])

  const load = async () => {
    try {
      setLoading(true)
      const params = new URLSearchParams()
      if (paymentFilter) params.set('payment_status', paymentFilter)
      if (dateFilter.from) params.set('date_from', dateFilter.from)
      if (dateFilter.to) params.set('date_to', dateFilter.to)
      params.set('limit', '500')

      const [purch, prods] = await Promise.all([
        request<CustomerPurchase[]>(`/api/bevi-stoq/customer-purchases?${params}`),
        request<Product[]>('/api/bevi-stoq/products?active_only=true&limit=1000')
      ])
      setPurchases(purch || [])
      setProducts(prods)
    } catch (error) {
      console.error('Load error:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleAdd = async () => {
    try {
      setError('')
      if (!formData.customer_name || !formData.customer_name.trim()) {
        setError('Customer Name is required')
        return
      }
      if (!formData.product_id) {
        setError('Product is required')
        return
      }
      if (!formData.quantity) {
        setError('Quantity is required')
        return
      }
      if (!formData.amount || isNaN(parseFloat(formData.amount))) {
        setError('Valid Amount is required')
        return
      }

      const payload = {
        customer_name: formData.customer_name,
        product_id: parseInt(formData.product_id),
        quantity: parseFloat(formData.quantity),
        unit: formData.unit,
        purchase_date: formData.purchase_date,
        payment_status: formData.payment_status,
        payment_method: formData.payment_method,
        amount: parseFloat(formData.amount),
        notes: formData.notes
      }

      if (isEditing && editingId) {
        await request(`/api/bevi-stoq/customer-purchases/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify(payload)
        })
      } else {
        await request('/api/bevi-stoq/customer-purchases', {
          method: 'POST',
          body: JSON.stringify(payload)
        })
      }

      setFormData({
        customer_name: '', product_id: '', quantity: '', unit: 'kg',
        purchase_date: new Date().toISOString().split('T')[0],
        payment_status: 'pending', payment_method: 'cash', amount: '', notes: ''
      })
      setIsAdding(false)
      setIsEditing(false)
      setEditingId(null)
      load()
    } catch (error) {
      setError(`Error: ${error instanceof Error ? error.message : 'Failed to save purchase'}`)
    }
  }

  const handleEdit = (purchase: CustomerPurchase) => {
    setFormData({
      customer_name: purchase.customer_name,
      product_id: purchase.id?.toString() || '',
      quantity: purchase.quantity.toString(),
      unit: purchase.unit,
      purchase_date: purchase.purchase_date,
      payment_status: purchase.payment_status as 'pending' | 'paid' | 'overdue',
      payment_method: purchase.payment_method || 'cash',
      amount: purchase.amount.toString(),
      notes: purchase.notes || ''
    })
    setEditingId(purchase.id)
    setIsEditing(true)
    setIsAdding(true)
  }

  const handleDelete = async (id: number) => {
    try {
      await request(`/api/bevi-stoq/customer-purchases/${id}`, { method: 'DELETE' })
      load()
      setDeleteConfirm(null)
    } catch (error) {
      setError(`Delete error: ${error instanceof Error ? error.message : 'Failed to delete'}`)
    }
  }

  const getPaymentStatusColor = (status: string) => {
    switch (status) {
      case 'paid':
        return 'bg-green-500/20 text-green-300'
      case 'pending':
        return 'bg-orange-500/20 text-orange-300'
      case 'overdue':
        return 'bg-red-500/20 text-red-300'
      default:
        return 'bg-gray-500/20 text-gray-300'
    }
  }

  const totalAmount = purchases.reduce((sum, p) => sum + p.amount, 0)
  const paidAmount = purchases
    .filter(p => p.payment_status === 'paid')
    .reduce((sum, p) => sum + p.amount, 0)
  const pendingAmount = purchases
    .filter(p => p.payment_status === 'pending' || p.payment_status === 'overdue')
    .reduce((sum, p) => sum + p.amount, 0)

  if (loading) return <Spinner label="Loading purchases..." />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-3xl text-latte">Customer Purchases</h1>
        <Button onClick={() => setIsAdding(true)}>+ Record Purchase</Button>
      </div>

      <Card>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <p className="text-xs text-latte/60">Total Amount</p>
            <p className="mt-2 text-2xl font-bold text-gold">₹{totalAmount.toLocaleString()}</p>
          </div>
          <div>
            <p className="text-xs text-latte/60">Paid</p>
            <p className="mt-2 text-2xl font-bold text-green-400">₹{paidAmount.toLocaleString()}</p>
          </div>
          <div>
            <p className="text-xs text-latte/60">Pending</p>
            <p className="mt-2 text-2xl font-bold text-orange-400">₹{pendingAmount.toLocaleString()}</p>
          </div>
        </div>
      </Card>

      <Card>
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Field label="Payment Status">
              <Select
                value={paymentFilter}
                onChange={(e: any) => setPaymentFilter(e.target.value)}
                options={[
                  { value: '', label: 'All' },
                  { value: 'paid', label: 'Paid' },
                  { value: 'pending', label: 'Pending' },
                  { value: 'overdue', label: 'Overdue' }
                ]}
              />
            </Field>
            <Field label="From Date">
              <Input
                type="date"
                value={dateFilter.from}
                onChange={(e: any) => setDateFilter({ ...dateFilter, from: e.target.value })}
              />
            </Field>
            <Field label="To Date">
              <Input
                type="date"
                value={dateFilter.to}
                onChange={(e: any) => setDateFilter({ ...dateFilter, to: e.target.value })}
              />
            </Field>
          </div>
        </div>
      </Card>

      {purchases.length > 0 ? (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-caramel/15">
                <tr>
                  <th className="py-3 text-left text-latte/60">Date</th>
                  <th className="py-3 text-left text-latte/60">Customer</th>
                  <th className="py-3 text-left text-latte/60">Product</th>
                  <th className="py-3 text-right text-latte/60">Quantity</th>
                  <th className="py-3 text-right text-latte/60">Amount</th>
                  <th className="py-3 text-left text-latte/60">Status</th>
                  <th className="py-3 text-left text-latte/60">Payment Method</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-caramel/10">
                {purchases.map((purchase) => (
                  <tr key={purchase.id} className="hover:bg-espresso/20 group">
                    <td className="py-3 text-latte/70">
                      {new Date(purchase.purchase_date).toLocaleDateString()}
                    </td>
                    <td className="py-3 text-latte font-medium">{purchase.customer_name}</td>
                    <td className="py-3 text-latte/70">{purchase.product_name}</td>
                    <td className="py-3 text-right text-latte">
                      {purchase.quantity} {purchase.unit}
                    </td>
                    <td className="py-3 text-right font-medium text-gold">
                      ₹{purchase.amount.toLocaleString()}
                    </td>
                    <td className="py-3">
                      <span className={cx('rounded-full px-2.5 py-0.5 text-xs font-medium', getPaymentStatusColor(purchase.payment_status))}>
                        {purchase.payment_status.toUpperCase()}
                      </span>
                    </td>
                    <td className="py-3 text-latte/70 flex gap-2">
                      <button
                        onClick={() => handleEdit(purchase)}
                        className="p-1 text-latte/60 hover:text-gold transition opacity-0 group-hover:opacity-100"
                        title="Edit"
                      >
                        <Edit2 size={14} />
                      </button>
                      <button
                        onClick={() => setDeleteConfirm(purchase.id)}
                        className="p-1 text-latte/60 hover:text-red-400 transition opacity-0 group-hover:opacity-100"
                        title="Delete"
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        <EmptyState
          title="No purchases yet"
          hint="Record customer purchases to track payments and inventory impact"
          action={<Button onClick={() => setIsAdding(true)}>+ Record Purchase</Button>}
        />
      )}

      <Modal
        open={isAdding}
        onClose={() => {
          setIsAdding(false)
          setIsEditing(false)
          setEditingId(null)
          setError('')
          setFormData({
            customer_name: '', product_id: '', quantity: '', unit: 'kg',
            purchase_date: new Date().toISOString().split('T')[0],
            payment_status: 'pending', payment_method: 'cash', amount: '', notes: ''
          })
        }}
        title={isEditing ? 'Edit Customer Purchase' : 'Record Customer Purchase'}
      >
        <form
          onSubmit={(e: any) => {
            e.preventDefault()
            handleAdd()
          }}
          className="space-y-4"
        >
          {error && (
            <div className="rounded-lg bg-red-500/20 px-3 py-2 text-sm text-red-300">
              {error}
            </div>
          )}
          <Field label="Customer Name *">
            <Input
              placeholder="e.g. ABC Foods"
              value={formData.customer_name}
              onChange={(e: any) => setFormData({ ...formData, customer_name: e.target.value })}
              required
            />
          </Field>

          <Field label="Product *">
            <Select
              value={formData.product_id}
              onChange={(e: any) => setFormData({ ...formData, product_id: e.target.value })}
              options={products.map(p => ({ value: p.id.toString(), label: p.name }))}
              required
            />
          </Field>

          <Field label="Quantity *">
            <Input
              type="number"
              placeholder="e.g. 100"
              value={formData.quantity}
              onChange={(e: any) => setFormData({ ...formData, quantity: e.target.value })}
              required
            />
          </Field>

          <Field label="Unit *">
            <Select
              value={formData.unit}
              onChange={(e: any) => setFormData({ ...formData, unit: e.target.value })}
              options={[
                { value: 'kg', label: 'kg' },
                { value: 'g', label: 'g' },
                { value: 'pcs', label: 'pcs' },
                { value: 'litre', label: 'litre' }
              ]}
            />
          </Field>

          <Field label="Purchase Date *">
            <Input
              type="date"
              value={formData.purchase_date}
              onChange={(e: any) => setFormData({ ...formData, purchase_date: e.target.value })}
              required
            />
          </Field>

          <Field label="Amount (₹)">
            <Input
              type="number"
              placeholder="₹0.00"
              value={formData.amount}
              onChange={(e: any) => setFormData({ ...formData, amount: e.target.value })}
              step="0.01"
            />
          </Field>

          <Field label="Payment Status">
            <Select
              value={formData.payment_status}
              onChange={(e: any) => setFormData({ ...formData, payment_status: e.target.value as any })}
              options={[
                { value: 'paid', label: 'Paid' },
                { value: 'pending', label: 'Pending' },
                { value: 'overdue', label: 'Overdue' }
              ]}
            />
          </Field>

          <Field label="Payment Method">
            <Select
              value={formData.payment_method}
              onChange={(e: any) => setFormData({ ...formData, payment_method: e.target.value })}
              options={[
                { value: 'cash', label: 'Cash' },
                { value: 'online', label: 'Online Transfer' },
                { value: 'netbanking', label: 'Net Banking' },
                { value: 'cheque', label: 'Cheque' },
                { value: 'other', label: 'Other' }
              ]}
            />
          </Field>

          <Field label="Notes">
            <Input
              placeholder="Optional notes..."
              value={formData.notes}
              onChange={(e: any) => setFormData({ ...formData, notes: e.target.value })}
            />
          </Field>

          <div className="flex gap-3">
            <Button variant="ghost" onClick={() => setIsAdding(false)} type="button">
              Cancel
            </Button>
            <Button type="submit" className="flex-1">
              {isEditing ? 'Update' : 'Record'} Purchase
            </Button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        open={deleteConfirm !== null}
        title="Delete Purchase?"
        message="This purchase record will be permanently deleted."
        confirmLabel="Delete"
        onConfirm={() => {
          if (deleteConfirm) {
            handleDelete(deleteConfirm)
          }
        }}
        onCancel={() => setDeleteConfirm(null)}
      />
    </div>
  )
}
