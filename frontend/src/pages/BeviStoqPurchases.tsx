import { Plus, DollarSign, Edit2, Trash2, X } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api } from '../lib/api'
import { EmptyState, Spinner } from '../components/ui'
import { useToast } from '../lib/toast'
import { UnitSelect } from '../lib/units'

interface CustomerPurchase {
  id: number
  contact_id: number | null
  customer_name: string
  product_id: number
  quantity: number
  unit: string | null
  purchase_date: string
  payment_status: string
  payment_method: string | null
  amount: number
  notes: string | null
  created_at: string
}

interface Product {
  id: number
  name: string
  default_unit: string
}

export function BeviStoqPurchases() {
  const toast = useToast()
  const [purchases, setPurchases] = useState<CustomerPurchase[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [filterStatus, setFilterStatus] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [formData, setFormData] = useState({
    customer_name: '',
    contact_id: '',
    product_id: 0,
    quantity: '',
    unit: '',
    purchase_date: new Date().toISOString().split('T')[0],
    payment_status: 'pending',
    payment_method: '',
    amount: '',
    notes: '',
  })

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const [purRes, prodRes] = await Promise.all([
        api.get<CustomerPurchase[]>('/api/bevi-stoq/customer-purchases'),
        api.get<Product[]>('/api/bevi-stoq/products'),
      ])
      setPurchases(purRes || [])
      setProducts(prodRes || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load purchases')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: any) => {
    e.preventDefault()
    if (submitting) return
    setSubmitting(true)

    // Validation
    if (!formData.customer_name.trim()) {
      setError('Customer Name is required')
      setSubmitting(false)
      return
    }
    if (!formData.product_id) {
      setError('Product is required')
      setSubmitting(false)
      return
    }
    if (!formData.quantity || parseFloat(formData.quantity) <= 0) {
      setError('Quantity must be a positive number')
      setSubmitting(false)
      return
    }
    if (!formData.unit) {
      setError('Unit is required')
      setSubmitting(false)
      return
    }
    if (!formData.purchase_date) {
      setError('Date is required')
      setSubmitting(false)
      return
    }
    if (formData.amount && isNaN(parseFloat(formData.amount))) {
      setError('Amount must be a valid number')
      setSubmitting(false)
      return
    }

    try {
      const quantity = parseFloat(formData.quantity)
      const amountStr = formData.amount.trim()
      const amount = amountStr ? parseFloat(amountStr) : null

      if (isNaN(quantity) || quantity <= 0) {
        setError('Quantity must be a valid positive number')
        setSubmitting(false)
        return
      }
      if (amount !== null && isNaN(amount)) {
        setError('Amount must be a valid number')
        setSubmitting(false)
        return
      }
      if (amount !== null && amount < 0) {
        setError('Amount cannot be negative')
        setSubmitting(false)
        return
      }

      const payload = {
        customer_name: formData.customer_name.trim(),
        contact_id: formData.contact_id ? parseInt(formData.contact_id) : null,
        product_id: parseInt(formData.product_id as any),
        quantity: quantity,
        unit: formData.unit || null,
        purchase_date: formData.purchase_date,
        payment_status: formData.payment_status || 'pending',
        payment_method: formData.payment_method || null,
        amount: amount,
        notes: formData.notes || null,
      }

      if (editingId) {
        console.log(`Updating purchase ${editingId}:`, payload)
        const response = await api.put(`/api/bevi-stoq/customer-purchases/${editingId}`, payload)
        console.log('Purchase updated:', response)
        toast.success('Purchase updated successfully')
      } else {
        console.log('Creating new purchase:', payload)
        const response = await api.post('/api/bevi-stoq/customer-purchases', payload)
        console.log('Purchase created:', response)
        toast.success('Purchase recorded successfully')
      }

      setFormData({
        customer_name: '',
        contact_id: '',
        product_id: 0,
        quantity: '',
        unit: '',
        purchase_date: new Date().toISOString().split('T')[0],
        payment_status: 'pending',
        payment_method: '',
        amount: '',
        notes: '',
      })
      setEditingId(null)
      setShowForm(false)
      setError(null)
      await fetchData()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to record purchase'
      console.error('Purchase error:', message, err)
      setError(message)
      toast.error(message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleUpdateStatus = async (id: number, status: string) => {
    try {
      await api.put(`/api/bevi-stoq/customer-purchases/${id}`, {
        payment_status: status,
      })
      await fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update purchase')
    }
  }

  const handleEdit = (purchase: CustomerPurchase) => {
    setFormData({
      customer_name: purchase.customer_name,
      contact_id: purchase.contact_id?.toString() || '',
      product_id: purchase.product_id,
      quantity: purchase.quantity.toString(),
      unit: purchase.unit || '',
      purchase_date: purchase.purchase_date.split('T')[0],
      payment_status: purchase.payment_status,
      payment_method: purchase.payment_method || '',
      amount: purchase.amount ? purchase.amount.toString() : '',
      notes: purchase.notes || '',
    })
    setEditingId(purchase.id)
    setShowForm(true)
  }

  const handleDelete = async (id: number) => {
    const purchase = purchases.find((p) => p.id === id)
    const confirmMsg = `⚠️ Delete this purchase?\n\nThis will:\n• Remove the purchase record\n• Restore ${purchase?.quantity} ${purchase?.unit} of ${getProductName(purchase?.product_id || 0)} back to inventory\n\nThis action cannot be undone.`

    if (!confirm(confirmMsg)) return
    try {
      await api.delete(`/api/bevi-stoq/customer-purchases/${id}`)
      toast.success('Purchase deleted and inventory restored')
      await fetchData()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete purchase'
      setError(message)
      toast.error(message)
    }
  }

  const getProductName = (id: number) => products.find((p) => p.id === id)?.name || 'Unknown'

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'paid':
        return 'bg-green-500/20 text-green-400'
      case 'pending':
        return 'bg-yellow-500/20 text-yellow-400'
      case 'overdue':
        return 'bg-red-500/20 text-red-400'
      default:
        return 'bg-latte/10 text-latte'
    }
  }

  let filtered = purchases
  if (filterStatus) filtered = filtered.filter((p) => p.payment_status === filterStatus)

  if (loading) return <Spinner label="Loading purchases…" />
  if (error) return <EmptyState emoji="⚠️" title="Error" hint={error} />

  const totalAmount = purchases.reduce((sum, p) => sum + (p.amount ?? 0), 0)
  const paidAmount = purchases.filter((p) => p.payment_status === 'paid').reduce((sum, p) => sum + (p.amount ?? 0), 0)
  const pendingAmount = purchases.filter((p) => p.payment_status === 'pending').reduce((sum, p) => sum + (p.amount ?? 0), 0)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-latte">Customer Purchases</h1>
          <p className="mt-1 text-sm text-latte/60">Track sales and payment status</p>
        </div>
        <button
          onClick={() => {
            setFormData({
              customer_name: '',
              contact_id: '',
              product_id: 0,
              quantity: '',
              unit: '',
              purchase_date: new Date().toISOString().split('T')[0],
              payment_status: 'pending',
              payment_method: '',
              amount: '',
              notes: '',
            })
            setEditingId(null)
            setShowForm(!showForm)
          }}
          className="flex items-center gap-2 rounded-lg bg-gold/20 px-4 py-2 text-sm font-medium text-gold hover:bg-gold/30"
        >
          <Plus size={16} />
          New Purchase
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
          <p className="text-xs uppercase tracking-wide text-latte/60">Total Sales</p>
          <p className="mt-1 text-2xl font-bold text-gold">₹{totalAmount.toFixed(2)}</p>
        </div>
        <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
          <p className="text-xs uppercase tracking-wide text-green-400">Paid</p>
          <p className="mt-1 text-2xl font-bold text-green-400">₹{paidAmount.toFixed(2)}</p>
        </div>
        <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
          <p className="text-xs uppercase tracking-wide text-yellow-400">Pending</p>
          <p className="mt-1 text-2xl font-bold text-yellow-400">₹{pendingAmount.toFixed(2)}</p>
        </div>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="rounded-lg border border-caramel/15 bg-espresso/40 p-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-latte">
              {editingId ? 'Edit Purchase' : 'New Purchase'}
            </h2>
            <button
              type="button"
              onClick={() => {
                setShowForm(false)
                setEditingId(null)
              }}
              className="text-latte/60 hover:text-latte"
            >
              <X size={20} />
            </button>
          </div>
          {error && (
            <div className="mb-4 rounded-lg bg-red-500/20 p-4 text-red-400">
              <p className="text-sm font-medium">Error: {error}</p>
            </div>
          )}
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-latte">Customer Name *</label>
                <input
                  type="text"
                  value={formData.customer_name}
                  onChange={(e) => setFormData({ ...formData, customer_name: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte placeholder-latte/40 focus:outline-none focus:ring-2 focus:ring-gold/50"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-latte">Contact ID</label>
                <input
                  type="number"
                  value={formData.contact_id}
                  onChange={(e) => setFormData({ ...formData, contact_id: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-latte">Product *</label>
                <select
                  value={formData.product_id}
                  onChange={(e) => {
                    const prodId = parseInt(e.target.value)
                    const prod = products.find((p) => p.id === prodId)
                    setFormData({
                      ...formData,
                      product_id: prodId,
                      unit: prod?.default_unit || formData.unit,
                    })
                  }}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                  required
                >
                  <option value={0}>Select product</option>
                  {products.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-latte">Quantity *</label>
                <input
                  type="text"
                  inputMode="decimal"
                  value={formData.quantity}
                  onChange={(e) => setFormData({ ...formData, quantity: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                  placeholder="e.g., 1.61"
                  required
                />
              </div>
              <UnitSelect
                value={formData.unit}
                onChange={(unit) => setFormData({ ...formData, unit })}
                label="Unit"
                required={true}
              />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-latte">Date *</label>
                <input
                  type="date"
                  value={formData.purchase_date}
                  onChange={(e) => setFormData({ ...formData, purchase_date: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-latte">Amount (₹) <span className="text-latte/60">(optional)</span></label>
                <input
                  type="text"
                  inputMode="decimal"
                  value={formData.amount}
                  onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                  placeholder="e.g., 500.50"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-latte">Status</label>
                <select
                  value={formData.payment_status}
                  onChange={(e) => setFormData({ ...formData, payment_status: e.target.value })}
                  className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                >
                  <option value="pending">Pending</option>
                  <option value="paid">Paid</option>
                  <option value="overdue">Overdue</option>
                </select>
              </div>
            </div>
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={submitting}
                className="rounded bg-gold/20 px-4 py-2 text-sm font-medium text-gold hover:bg-gold/30 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? 'Saving...' : editingId ? 'Update Purchase' : 'Record Purchase'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowForm(false)
                  setEditingId(null)
                }}
                disabled={submitting}
                className="rounded border border-caramel/30 px-4 py-2 text-sm font-medium text-latte/60 hover:bg-caramel/10 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Cancel
              </button>
            </div>
          </div>
        </form>
      )}

      {/* Filter */}
      <select
        value={filterStatus}
        onChange={(e) => setFilterStatus(e.target.value)}
        className="rounded bg-bean/50 px-3 py-2 text-sm text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
      >
        <option value="">All Statuses</option>
        <option value="paid">Paid</option>
        <option value="pending">Pending</option>
        <option value="overdue">Overdue</option>
      </select>

      {filtered.length === 0 ? (
        <EmptyState emoji="🛒" title="No purchases" hint="Record your first customer purchase" />
      ) : (
        <div className="space-y-3">
          {filtered.map((purchase) => (
            <div key={purchase.id} className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <DollarSign size={20} className="mt-1 text-gold/60" />
                  <div className="space-y-1">
                    <p className="font-semibold text-latte">{purchase.customer_name}</p>
                    <p className="text-sm text-latte/70">{getProductName(purchase.product_id)}</p>
                    <p className="text-xs text-latte/50">{new Date(purchase.purchase_date).toLocaleDateString()}</p>
                  </div>
                </div>
                <div className="text-right">
                  <div className="flex items-center justify-end gap-2 mb-2">
                    <button
                      onClick={() => handleEdit(purchase)}
                      className="rounded p-1 hover:bg-caramel/20 text-latte/60 hover:text-gold"
                      title="Edit purchase"
                    >
                      <Edit2 size={16} />
                    </button>
                    <button
                      onClick={() => handleDelete(purchase.id)}
                      className="rounded p-1 hover:bg-caramel/20 text-latte/60 hover:text-red-400"
                      title="Delete purchase"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                  <p className="text-lg font-bold text-gold">
                    {purchase.amount !== null ? `₹${purchase.amount.toFixed(2)}` : '—'}
                  </p>
                  <p className="text-xs text-latte/50">{purchase.quantity} {purchase.unit}</p>
                  <div className="mt-2">
                    <span className={`inline-block rounded px-2 py-1 text-xs font-medium ${getStatusColor(purchase.payment_status)}`}>
                      {purchase.payment_status.toUpperCase()}
                    </span>
                  </div>
                  {purchase.payment_status !== 'paid' && (
                    <button
                      onClick={() => handleUpdateStatus(purchase.id, 'paid')}
                      className="mt-2 block text-xs text-green-400 hover:text-green-300"
                    >
                      Mark Paid
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
