// Display formatting. The API speaks pounds and ISO dates; people read these.
const gbp = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' })
const whole = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', maximumFractionDigits: 0 })

export const money = value => (value === null || value === undefined ? '' : gbp.format(value))
export const pounds = value => (value === null || value === undefined ? '' : whole.format(value))

export const date = iso => {
  if (!iso) return ''
  return new Date(iso + 'T00:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

export const postcode = pc => {
  if (!pc) return ''
  const s = pc.replace(/\s+/g, '').toUpperCase()
  return s.length > 3 ? `${s.slice(0, -3)} ${s.slice(-3)}` : s
}

export const factor = f => `× ${Number(f).toFixed(3).replace(/0$/, '')}`

export const statusClass = code => ({ L: 'good', Q: 'todo', R: 'todo', X: 'bad', E: 'bad', D: 'bad' }[code] || 'todo')
