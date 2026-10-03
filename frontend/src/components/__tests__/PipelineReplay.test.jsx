import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import PipelineReplay, { labelFor } from '../PipelineReplay'

const trace = [
  { node: 'web_search', seconds: 12.4, models: [] },
  { node: 'swot_analysis', seconds: 8, models: ['groq/openai/gpt-oss-120b'] },
  { node: 'mvp_recommendation', seconds: 6.1, models: ['groq/openai/gpt-oss-20b', 'gemini/gemini-3.6'] },
]

describe('PipelineReplay', () => {
  it('renders nothing for reports without a trace', () => {
    expect(render(<PipelineReplay trace={undefined} />).container.firstChild).toBeNull()
    expect(render(<PipelineReplay trace={[]} />).container.firstChild).toBeNull()
  })

  it('summarises steps, models and total time', () => {
    render(<PipelineReplay trace={trace} />)
    const text = screen.getByTestId('pipeline-replay').textContent
    expect(text).toMatch(/3\s*steps/)
    expect(text).toMatch(/3\s*models/)
    expect(text).toMatch(/27s/)
  })

  it('lists each step with its model, and marks code-only steps', () => {
    render(<PipelineReplay trace={trace} />)
    fireEvent.click(screen.getByText('Show steps'))
    expect(screen.getByText('SWOT and risks')).toBeInTheDocument()
    expect(screen.getByText(/gpt-oss-120b · 8\.0s/)).toBeInTheDocument()
    expect(screen.getByText(/code only · 12\.4s/)).toBeInTheDocument()
  })

  it('falls back to a readable label for unknown step ids', () => {
    expect(labelFor('some_new_step')).toBe('some new step')
  })
})
