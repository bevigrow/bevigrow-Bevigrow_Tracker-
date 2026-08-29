import { useEffect, useState } from 'react'
import { request } from '../lib/api'
import { Button, Card, Input, Field, Select, Spinner, cx } from '../components/ui'

interface Category {
  id: number
  name: string
}

interface Product {
  id: number
  name: string
  active: boolean
}

interface DiagnosticResult {
  category: string
  searched_name: string
  exact_matches: Product[]
  similar_matches: Product[]
  all_in_category: Product[]
}

export function BeviStoqDiagnostics() {
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedCategory, setSelectedCategory] = useState('')
  const [productName, setProductName] = useState('')
  const [result, setResult] = useState<DiagnosticResult | null>(null)
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    loadCategories()
  }, [])

  const loadCategories = async () => {
    try {
      const cats = await request<Category[]>('/api/bevi-stoq/categories?active_only=false&limit=1000')
      setCategories(cats)
    } catch (err) {
      setError(`Error loading categories: ${err instanceof Error ? err.message : 'Unknown'}`)
    } finally {
      setLoading(false)
    }
  }

  const handleCheck = async () => {
    try {
      setError('')
      if (!selectedCategory || !productName.trim()) {
        setError('Select a category and enter product name')
        return
      }

      setChecking(true)
      const res = await request<DiagnosticResult>(
        `/api/bevi-stoq/products/diagnostic/check?category_id=${selectedCategory}&product_name=${encodeURIComponent(productName)}`
      )
      setResult(res)
    } catch (err) {
      setError(`Error: ${err instanceof Error ? err.message : 'Unknown'}`)
    } finally {
      setChecking(false)
    }
  }

  if (loading) return <Spinner label="Loading..." />

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl text-latte">🔍 Diagnostics</h1>
        <p className="mt-2 text-sm text-latte/60">Check what products exist in your database to troubleshoot duplicate errors</p>
      </div>

      <Card className="bg-amber-500/10 border border-amber-500/30 p-4">
        <p className="text-sm text-amber-200">
          <strong>If you're getting "Product already exists" errors:</strong> Use this tool to see all products in a category,
          including inactive/deleted ones. You can then deactivate old test data.
        </p>
      </Card>

      <Card>
        <div className="space-y-4">
          <Field label="Category">
            <Select
              value={selectedCategory}
              onChange={(e: any) => setSelectedCategory(e.target.value)}
              options={[
                { value: '', label: 'Select category' },
                ...categories.map(c => ({ value: c.id.toString(), label: c.name }))
              ]}
            />
          </Field>

          <Field label="Product Name to Search">
            <Input
              placeholder="e.g. Black Pepper"
              value={productName}
              onChange={(e: any) => setProductName(e.target.value)}
              onKeyPress={(e: any) => e.key === 'Enter' && handleCheck()}
            />
          </Field>

          {error && (
            <div className="rounded-lg bg-red-500/20 px-3 py-2 text-sm text-red-300">
              {error}
            </div>
          )}

          <Button
            onClick={handleCheck}
            disabled={checking || !selectedCategory || !productName.trim()}
            className="w-full"
          >
            {checking ? 'Checking...' : 'Check Database'}
          </Button>
        </div>
      </Card>

      {result && (
        <Card>
          <div className="space-y-6">
            <div>
              <h3 className="text-sm font-semibold text-latte mb-3">Exact Matches</h3>
              {result.exact_matches.length > 0 ? (
                <div className="space-y-2">
                  {result.exact_matches.map(p => (
                    <div
                      key={p.id}
                      className={cx(
                        'rounded-lg p-3',
                        p.active
                          ? 'bg-green-500/10 border border-green-500/30'
                          : 'bg-gray-500/10 border border-gray-500/30'
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium text-latte">{p.name}</p>
                          <p className={cx('text-xs', p.active ? 'text-green-400' : 'text-gray-400')}>
                            ID: {p.id} • {p.active ? 'ACTIVE' : 'INACTIVE'}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-latte/60">No exact matches found</p>
              )}
            </div>

            {result.similar_matches.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-latte mb-3">Similar Matches</h3>
                <div className="space-y-2">
                  {result.similar_matches.map(p => (
                    <div
                      key={p.id}
                      className={cx(
                        'rounded-lg p-3',
                        p.active
                          ? 'bg-blue-500/10 border border-blue-500/30'
                          : 'bg-gray-500/10 border border-gray-500/30'
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium text-latte">{p.name}</p>
                          <p className={cx('text-xs', p.active ? 'text-blue-400' : 'text-gray-400')}>
                            ID: {p.id} • {p.active ? 'ACTIVE' : 'INACTIVE'}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {result.all_in_category.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-latte mb-3">All Products in "{result.category}"</h3>
                <div className="space-y-1 text-sm">
                  <p className="text-latte/60">Total: {result.all_in_category.length}</p>
                  <p className="text-green-400">Active: {result.all_in_category.filter(p => p.active).length}</p>
                  <p className="text-gray-400">Inactive: {result.all_in_category.filter(p => !p.active).length}</p>
                </div>
              </div>
            )}

            <div className="border-t border-caramel/15 pt-4">
              <p className="text-xs text-latte/60">
                <strong>💡 Tip:</strong> If you see inactive products with the same name, you can delete them from the Products page.
                Active duplicates (especially test data) are likely causing your "already exists" errors.
              </p>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
