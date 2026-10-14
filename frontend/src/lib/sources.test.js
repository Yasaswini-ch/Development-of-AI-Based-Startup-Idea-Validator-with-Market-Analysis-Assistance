import { describe, expect, it } from 'vitest'
import { citedBySection } from './sources'

describe('citedBySection', () => {
  it('lists each section that cites a source, once, in the order given', () => {
    const cited = citedBySection([
      ['Market', { trends: [{ sourceIds: ['src-1', 'src-2'] }], marketSizeSourceIds: ['ignored'] }],
      ['SWOT', { strengths: [{ sourceIds: ['src-1'] }, { sourceIds: ['src-1'] }] }],
      ['MVP', null],
    ])
    expect(cited.get('src-1')).toEqual(['Market', 'SWOT'])
    expect(cited.get('src-2')).toEqual(['Market'])
    expect(cited.has('ignored')).toBe(false)
  })

  it('ignores sections that failed or hold no citations', () => {
    expect(citedBySection([['GTM', undefined], ['Revenue', { models: [] }]]).size).toBe(0)
  })
})
