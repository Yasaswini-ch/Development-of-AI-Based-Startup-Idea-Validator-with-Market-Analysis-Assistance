import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import LandingPage from '../LandingPage'

function renderLanding() {
  return render(
    <LandingPage onStart={vi.fn()} currentUser={null} onSignIn={vi.fn()} onSignOut={vi.fn()} apiUrl="http://x" onAuthenticated={vi.fn()} />,
  )
}

describe('Landing page How it works', () => {
  it('opens on step 1 and switches the detail panel when another step is clicked', () => {
    renderLanding()
    const tabs = screen.getAllByRole('tab')
    expect(tabs).toHaveLength(4)
    expect(tabs[0]).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tabpanel')).toHaveTextContent('Describe your idea')

    fireEvent.click(tabs[2])
    expect(tabs[2]).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tabpanel')).toHaveTextContent('A verdict, not a guess')
    expect(screen.getByRole('tabpanel')).toHaveTextContent('Grounded vs Inferred')
  })

  it('moves between steps with the arrow keys', () => {
    renderLanding()
    const tabs = screen.getAllByRole('tab')
    fireEvent.keyDown(tabs[0], { key: 'ArrowRight' })
    expect(tabs[1]).toHaveAttribute('aria-selected', 'true')
    fireEvent.keyDown(tabs[1], { key: 'ArrowLeft' })
    fireEvent.keyDown(tabs[0], { key: 'ArrowLeft' })
    expect(tabs[3]).toHaveAttribute('aria-selected', 'true')
  })
})
