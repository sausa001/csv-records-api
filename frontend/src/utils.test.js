import { describe, expect, it } from 'vitest'
import { buildQuery, errorMessage, formatCompactINR, toPayload, validateRecord, EMPTY_RECORD } from './utils.js'

describe('buildQuery', () => {
  it('skips empty values', () => {
    expect(buildQuery({ page: 1, search: '', city: null, active: false })).toBe('?page=1&active=false')
  })
  it('returns empty string when nothing is set', () => {
    expect(buildQuery({ search: '' })).toBe('')
  })
})

describe('formatCompactINR', () => {
  it('formats lakhs and crores', () => {
    expect(formatCompactINR(8450000)).toBe('₹84.5L')
    expect(formatCompactINR(21950000)).toBe('₹2.2Cr')
    expect(formatCompactINR(1000000)).toBe('₹10L')
  })
})

describe('errorMessage', () => {
  it('reads string detail', () => {
    expect(errorMessage({ detail: 'Record 9 not found' }, 404)).toBe('Record 9 not found')
  })
  it('flattens FastAPI validation errors', () => {
    const body = { detail: [{ loc: ['body', 'email'], msg: 'value is not a valid email address' }] }
    expect(errorMessage(body, 422)).toBe('email: value is not a valid email address')
  })
  it('falls back to status', () => {
    expect(errorMessage(null, 500)).toBe('Request failed (500)')
  })
})

describe('record form', () => {
  const valid = {
    name: ' Test User ', email: 'test@example.com', department: 'Engineering', role: 'SRE',
    city: 'Pune', salary: '1200000', joining_date: '2024-01-15', active: true,
  }
  it('converts form strings to API types', () => {
    expect(toPayload(valid)).toEqual({ ...valid, name: 'Test User', salary: 1200000 })
  })
  it('accepts a valid record', () => {
    expect(validateRecord(valid)).toEqual({})
  })
  it('flags missing and invalid fields', () => {
    const errors = validateRecord({ ...EMPTY_RECORD, email: 'nope', salary: '-5' })
    expect(Object.keys(errors).sort()).toEqual(
      ['city', 'department', 'email', 'joining_date', 'name', 'role', 'salary'],
    )
  })
})
