export const STANDARD_UNITS = [
  'g',
  'kg',
  'tonne',
  'pcs',
  'litre',
  'ml',
  'box',
  'bag',
]

export const UnitSelect = ({ value, onChange, label = 'Unit', required = false, className = '' }: {
  value: string
  onChange: (value: string) => void
  label?: string
  required?: boolean
  className?: string
}) => (
  <div className={className}>
    <label className="block text-sm font-medium text-latte">{label}{required ? ' *' : ''}</label>
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="mt-1 w-full rounded bg-bean/50 px-3 py-2 text-latte focus:outline-none focus:ring-2 focus:ring-gold/50"
      required={required}
    >
      <option value="">Select unit</option>
      {STANDARD_UNITS.map((unit) => (
        <option key={unit} value={unit}>
          {unit}
        </option>
      ))}
    </select>
  </div>
)
