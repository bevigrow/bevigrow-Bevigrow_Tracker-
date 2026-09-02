import { Plus, Edit2, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api } from '../lib/api'
import { EmptyState, Spinner } from '../components/ui'
import { useToast } from '../lib/toast'

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

interface Combo {
  id: number
  name: string
  description: string | null
}

interface PurchaseLine {
  product_id: number | null
  combo_id: number | null
  quantity: string
  unit: string
  amount: string
}

export function BeviStoqPurchases() {
  const toast = useToast()
  const [purchases, setPurchases] = useState<CustomerPurchase[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [combos, setCombos] = useState<Combo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [filterStatus, setFilterStatus] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [formData, setFormData] = useState<{
    customer_name: string
    contact_id: string
    purchase_date: string
    payment_status: string
    payment_method: string
    notes: string
    lines: PurchaseLine[]
  }>({
    customer_name: '',
    contact_id: '',
    purchase_date: new Date().toISOString().split('T')[0],
    payment_status: 'pending',
    payment_method: '',
    notes: '',
    lines: [{ product_id: null, combo_id: null, quantity: '', unit: '', amount: '' }],
  })

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const [purRes, prodRes, comboRes] = await Promise.all([
        api.get<CustomerPurchase[]>('/api/bevi-stoq/customer-purchases'),
        api.get<Product[]>('/api/bevi-stoq/products'),
        api.get<Combo[]>('/api/bevi-stoq/combos'),
      ])
      setPurchases(purRes || [])
      setProducts(prodRes || [])
      setCombos(comboRes || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load purchases')
    } finally {
      setLoading(false)
    }
  }

  const getTotalAmount = (): number => {
    return formData.lines.reduce((sum, line) => {
      const amount = line.amount ? parseFloat(line.amount) : 0
      return sum + (isNaN(amount) ? 0 : amount)
    }, 0)
  }

  const getProductUnit = (productId: number): string => {
    return products.find((p) => p.id === productId)?.default_unit || ''
  }

  const handleAddLine = () => {
    setFormData({
      ...formData,
      lines: [...formData.lines, { product_id: null, combo_id: null, quantity: '', unit: '', amount: '' }],
    })
  }

  const handleRemoveLine = (idx: number) => {
    if (formData.lines.length === 1) {
      toast.error('At least one product is required')
      return
    }
    setFormData({
      ...formData,
      lines: formData.lines.filter((_, i) => i !== idx),
    })
  }

  const handleLineChange = (idx: number, field: keyof PurchaseLine, value: any) => {
    const newLines = [...formData.lines]
    const updatedLine = { ...newLines[idx], [field]: value } as PurchaseLine

    if (field === 'product_id' && value) {
      updatedLine.unit = getProductUnit(parseInt(value))
      updatedLine.combo_id = null
    }

    if (field === 'combo_id' && value) {
      updatedLine.product_id = null
    }

    newLines[idx] = updatedLine
    setFormData({ ...formData, lines: newLines })
  }

  const handleSubmit = async (e: any) => {
    e.preventDefault()
    if (submitting) return
    setSubmitting(true)
    setError(null)

    try {
      // Validation
      if (!formData.customer_name.trim()) {
        setError('Customer Name is required')
        setSubmitting(false)
        return
      }

      const validLines = formData.lines.filter((l) => l.product_id || l.combo_id)
      if (validLines.length === 0) {
        setError('At least one product or combo is required')
        setSubmitting(false)
        return
      }

      for (const line of validLines) {
        if (!line.quantity || parseFloat(line.quantity) <= 0) {
          setError('All quantities must be positive numbers')
          setSubmitting(false)
          return
        }
        if (line.product_id && !line.unit) {
          setError('Unit is required for products')
          setSubmitting(false)
          return
        }
      }

      if (!formData.purchase_date) {
        setError('Date is required')
        setSubmitting(false)
        return
      }

      // Create a purchase for each line (products and combos)
      let savedCount = 0
      for (const line of validLines) {
        const quantity = parseFloat(line.quantity)
        const amount = line.amount ? parseFloat(line.amount) : null

        if (line.product_id || line.combo_id) {
          const payload = {
            customer_name: formData.customer_name.trim(),
            contact_id: formData.contact_id ? parseInt(formData.contact_id) : null,
            product_id: line.product_id || null,
            combo_id: line.combo_id || null,
            quantity: quantity,
            unit: line.unit || null,
            purchase_date: formData.purchase_date,
            payment_status: formData.payment_status || 'pending',
            payment_method: formData.payment_method || null,
            amount: amount,
            notes: formData.notes || null,
          }

          try {
            if (editingId && validLines.length === 1) {
              await api.put(`/api/bevi-stoq/customer-purchases/${editingId}`, payload)
            } else {
              await api.post('/api/bevi-stoq/customer-purchases', payload)
            }
            savedCount++
          } catch (lineErr) {
            const msg = lineErr instanceof Error ? lineErr.message : 'Failed to save purchase line'
            toast.error(`Line ${savedCount + 1}: ${msg}`)
            throw lineErr
          }
        }
      }

      await fetchData()
      toast.success(`${savedCount} purchase(s) recorded successfully`)

      setFormData({
        customer_name: '',
        contact_id: '',
        purchase_date: new Date().toISOString().split('T')[0],
        payment_status: 'pending',
        payment_method: '',
        notes: '',
        lines: [{ product_id: null, combo_id: null, quantity: '', unit: '', amount: '' }],
      })
      setEditingId(null)
      setShowForm(false)
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

  const handleEdit = (purchase: CustomerPurchase) => {
    const lines: PurchaseLine[] = [
      {
        product_id: purchase.product_id,
        combo_id: null,
        quantity: purchase.quantity.toString(),
        unit: purchase.unit || '',
        amount: purchase.amount?.toString() || '',
      },
    ]
    setFormData({
      customer_name: purchase.customer_name,
      contact_id: purchase.contact_id?.toString() || '',
      purchase_date: purchase.purchase_date.split('T')[0],
      payment_status: purchase.payment_status,
      payment_method: purchase.payment_method || '',
      notes: purchase.notes || '',
      lines,
    })
    setEditingId(purchase.id)
    setShowForm(true)
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this purchase?')) return
    try {
      await api.delete(`/api/bevi-stoq/customer-purchases/${id}`)
      await fetchData()
      toast.success('Purchase deleted')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete purchase'
      setError(message)
      toast.error(message)
    }
  }

  const filteredPurchases = purchases.filter((p) => !filterStatus || p.payment_status === filterStatus)
  const totalSales = filteredPurchases.reduce((sum, p) => sum + (p.amount || 0), 0)
  const paidSales = filteredPurchases.filter((p) => p.payment_status === 'paid').reduce((sum, p) => sum + (p.amount || 0), 0)
  const pendingSales = filteredPurchases.filter((p) => p.payment_status === 'pending').reduce((sum, p) => sum + (p.amount || 0), 0)

  if (loading) return <Spinner label="Loading purchases…" />
  if (error && !showForm) return <EmptyState emoji="⚠️" title="Error" hint={error} />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-latte">Customer Purchases</h1>
          <p className="mt-1 text-sm text-latte/60">Track sales and payment status</p>
        </div>
        <button
          onClick={() => {
            setShowForm(!showForm)
            setEditingId(null)
            setFormData({
              customer_name: '',
              contact_id: '',
              purchase_date: new Date().toISOString().split('T')[0],
              payment_status: 'pending',
              payment_method: '',
              notes: '',
              lines: [{ product_id: null, combo_id: null, quantity: '', unit: '', amount: '' }],
            })
          }}
          className="flex items-center gap-2 rounded-lg bg-gold/20 px-4 py-2 text-sm font-medium text-gold hover:bg-gold/30"
        >
          <Plus size={16} />
          New Purchase
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
          <p className="text-xs uppercase tracking-wide text-latte/60">Total Sales</p>
          <p className="mt-2 text-2xl font-bold text-latte">₹{totalSales.toFixed(2)}</p>
        </div>
        <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
          <p className="text-xs uppercase tracking-wide text-green-400">Paid</p>
          <p className="mt-2 text-2xl font-bold text-green-400">₹{paidSales.toFixed(2)}</p>
        </div>
        <div className="rounded-lg border border-caramel/15 bg-espresso/40 p-4">
          <p className="text-xs uppercase tracking-wide text-yellow-400">Pending</p>
          <p className="mt-2 text-2xl font-bold text-yellow-400">₹{pendingSales.toFixed(2)}</p>
        </div>
      </div>

      {/* New Purchase Form */}
      {showForm && (
        <form onSubmit={handleSubmit} className="rounded-lg border border-caramel/15 bg-espresso/40 p-6 space-y-4">
          <div className="mb-4 pb-4 border-b border-caramel/15">
            <h2 className="text-lg font-semibold text-latte">New Purchase</h2>
            {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
          </div>

          {/* Customer Info */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-latte mb-1">Customer Name *</label>
              <input
                type="text"
                value={formData.customer_name}
                onChange={(e) => setFormData({ ...formData, customer_name: e.target.value })}
                className="w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                placeholder="Enter customer name"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-latte mb-1">Contact ID (optional)</label>
              <input
                type="number"
                value={formData.contact_id}
                onChange={(e) => setFormData({ ...formData, contact_id: e.target.value })}
                className="w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                placeholder="Enter contact ID"
              />
            </div>
          </div>

          {/* Date and Payment */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label className="block text-sm font-medium text-latte mb-1">Date *</label>
              <input
                type="date"
                value={formData.purchase_date}
                onChange={(e) => setFormData({ ...formData, purchase_date: e.target.value })}
                className="w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-latte mb-1">Status</label>
              <select
                value={formData.payment_status}
                onChange={(e) => setFormData({ ...formData, payment_status: e.target.value })}
                className="w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
              >
                <option value="pending">Pending</option>
                <option value="paid">Paid</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-latte mb-1">Payment Method (optional)</label>
              <input
                type="text"
                value={formData.payment_method}
                onChange={(e) => setFormData({ ...formData, payment_method: e.target.value })}
                className="w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                placeholder="e.g., Cash, Card, UPI"
              />
            </div>
          </div>

          {/* Purchase Lines */}
          <div className="border-t border-caramel/15 pt-4">
            <h3 className="font-semibold text-latte mb-3">Products & Combos</h3>
            <div className="space-y-3">
              {formData.lines.map((line, idx) => (
                <div key={idx} className="rounded-lg border border-caramel/15 bg-bean/20 p-4">
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
                    <div>
                      <label className="block text-xs font-medium text-latte/60 mb-1">Product *</label>
                      <select
                        value={line.product_id || ''}
                        onChange={(e) => handleLineChange(idx, 'product_id', e.target.value ? parseInt(e.target.value) : null)}
                        className="w-full rounded bg-bean/50 px-3 py-2 text-sm text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                      >
                        <option value="">Select product</option>
                        {products.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-latte/60 mb-1">or Combo</label>
                      <select
                        value={line.combo_id || ''}
                        onChange={(e) => handleLineChange(idx, 'combo_id', e.target.value ? parseInt(e.target.value) : null)}
                        className="w-full rounded bg-bean/50 px-3 py-2 text-sm text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                      >
                        <option value="">Select combo</option>
                        {combos.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-latte/60 mb-1">Qty *</label>
                      <input
                        type="number"
                        step="0.01"
                        value={line.quantity}
                        onChange={(e) => handleLineChange(idx, 'quantity', e.target.value)}
                        className="w-full rounded bg-bean/50 px-3 py-2 text-sm text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                        placeholder="1.61"
                        required
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-latte/60 mb-1">Unit *</label>
                      <select
                        value={line.unit}
                        onChange={(e) => handleLineChange(idx, 'unit', e.target.value)}
                        className="w-full rounded bg-bean/50 px-3 py-2 text-sm text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                        required
                      >
                        <option value="">Select unit</option>
                        <option value="g">g</option>
                        <option value="kg">kg</option>
                        <option value="tonne">tonne</option>
                        <option value="ml">ml</option>
                        <option value="litre">litre</option>
                        <option value="pcs">pcs</option>
                        <option value="box">box</option>
                        <option value="bag">bag</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-latte/60 mb-1">Amount (₹)</label>
                      <input
                        type="number"
                        step="0.01"
                        value={line.amount}
                        onChange={(e) => handleLineChange(idx, 'amount', e.target.value)}
                        className="w-full rounded bg-bean/50 px-3 py-2 text-sm text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
                        placeholder="500.50"
                      />
                    </div>
                  </div>

                  {formData.lines.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveLine(idx)}
                      className="mt-2 text-xs text-red-400 hover:text-red-300"
                    >
                      Remove line
                    </button>
                  )}
                </div>
              ))}
            </div>

            <button
              type="button"
              onClick={handleAddLine}
              className="mt-3 text-sm text-gold hover:text-gold/80 font-medium"
            >
              + Add Product
            </button>
          </div>

          {/* Notes */}
          <div>
            <label className="block text-sm font-medium text-latte mb-1">Notes (optional)</label>
            <textarea
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              className="w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
              placeholder="Add any notes..."
              rows={3}
            />
          </div>

          {/* Total */}
          <div className="border-t border-caramel/15 pt-4">
            <div className="flex justify-between items-center mb-4">
              <span className="text-sm font-medium text-latte">Total Amount:</span>
              <span className="text-2xl font-bold text-gold">₹{getTotalAmount().toFixed(2)}</span>
            </div>

            <div className="flex gap-3">
              <button
                type="submit"
                disabled={submitting}
                className="flex-1 rounded bg-gold/20 px-4 py-2 text-sm font-medium text-gold hover:bg-gold/30 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? 'Recording...' : 'Record Purchase'}
              </button>
              <button
                type="button"
                onClick={() => setShowForm(false)}
                disabled={submitting}
                className="flex-1 rounded border border-caramel/30 px-4 py-2 text-sm font-medium text-latte/60 hover:bg-caramel/10 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Cancel
              </button>
            </div>
          </div>
        </form>
      )}

      {/* Filter */}
      <div className="flex gap-2">
        <button
          onClick={() => setFilterStatus('')}
          className={`px-3 py-1 rounded text-sm font-medium transition ${
            filterStatus === '' ? 'bg-gold/20 text-gold border border-gold/30' : 'text-latte/60 hover:text-latte'
          }`}
        >
          All
        </button>
        <button
          onClick={() => setFilterStatus('paid')}
          className={`px-3 py-1 rounded text-sm font-medium transition ${
            filterStatus === 'paid' ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'text-latte/60 hover:text-latte'
          }`}
        >
          Paid
        </button>
        <button
          onClick={() => setFilterStatus('pending')}
          className={`px-3 py-1 rounded text-sm font-medium transition ${
            filterStatus === 'pending' ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30' : 'text-latte/60 hover:text-latte'
          }`}
        >
          Pending
        </button>
      </div>

      {/* Purchases List */}
      {filteredPurchases.length === 0 ? (
        <EmptyState emoji="📋" title="No purchases" hint="Record your first purchase to get started" />
      ) : (
        <div className="rounded-lg border border-caramel/15 bg-espresso/40 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-caramel/15">
                  <th className="px-4 py-3 text-left text-latte/60">Customer</th>
                  <th className="px-4 py-3 text-left text-latte/60">Product</th>
                  <th className="px-4 py-3 text-left text-latte/60">Qty</th>
                  <th className="px-4 py-3 text-left text-latte/60">Amount</th>
                  <th className="px-4 py-3 text-left text-latte/60">Status</th>
                  <th className="px-4 py-3 text-left text-latte/60">Date</th>
                  <th className="px-4 py-3 text-right text-latte/60">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-caramel/15">
                {filteredPurchases.map((purchase) => (
                  <tr key={purchase.id} className="hover:bg-bean/30 transition">
                    <td className="px-4 py-3 text-latte">{purchase.customer_name}</td>
                    <td className="px-4 py-3 text-latte/70">{products.find((p) => p.id === purchase.product_id)?.name || 'Unknown'}</td>
                    <td className="px-4 py-3 text-latte/70">
                      {purchase.quantity} {purchase.unit}
                    </td>
                    <td className="px-4 py-3 text-latte font-medium">₹{(purchase.amount || 0).toFixed(2)}</td>
                    <td className="px-4 py-3">
                      <select
                        value={purchase.payment_status}
                        onChange={(e) =>
                          api
                            .put(`/api/bevi-stoq/customer-purchases/${purchase.id}`, { payment_status: e.target.value })
                            .then(() => fetchData())
                            .catch((err) => toast.error(err.message))
                        }
                        className={`rounded px-2 py-1 text-xs font-medium border-0 focus:outline-none focus:ring-2 focus:ring-gold/50 ${
                          purchase.payment_status === 'paid'
                            ? 'bg-green-500/20 text-green-400'
                            : 'bg-yellow-500/20 text-yellow-400'
                        }`}
                      >
                        <option value="pending">Pending</option>
                        <option value="paid">Paid</option>
                      </select>
                    </td>
                    <td className="px-4 py-3 text-latte/70 text-xs">{new Date(purchase.purchase_date).toLocaleDateString()}</td>
                    <td className="px-4 py-3 text-right space-x-2">
                      <button
                        onClick={() => handleEdit(purchase)}
                        className="text-blue-400 hover:text-blue-300 inline-block"
                      >
                        <Edit2 size={16} />
                      </button>
                      <button
                        onClick={() => handleDelete(purchase.id)}
                        className="text-red-400 hover:text-red-300 inline-block"
                      >
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
