import { expect, test } from 'vitest'
import { formatMoney, formatPercent, formatScore, humanizeReason } from './format'

test('formats API-returned money, risk percentages, and RS20 for display only', () => {
  expect(formatMoney('8500')).toBe('$8,500.00')
  expect(formatPercent('8.456')).toBe('8.46%')
  expect(formatScore('0.08421')).toBe('0.0842')
  expect(formatScore(null)).toBe('Not scored')
})

test('keeps machine reason codes readable without hiding their meaning', () => {
  expect(humanizeReason('SECTOR_LIMIT')).toBe('Sector limit reached')
  expect(humanizeReason('SOME_NEW_STATUS')).toBe('some new status')
})
