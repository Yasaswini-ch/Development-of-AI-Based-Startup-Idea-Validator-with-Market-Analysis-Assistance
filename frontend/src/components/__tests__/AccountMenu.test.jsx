import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import AccountMenu from '../AccountMenu'

const user = { email: 'founder.test@example.com', isAdmin: false }
const admin = { email: 'admin.test@example.com', isAdmin: true }

describe('AccountMenu', () => {
  it('shows the account button but not the menu items until opened', () => {
    render(<AccountMenu currentUser={user} onNavigate={vi.fn()} onSignOut={vi.fn()} />)
    expect(screen.getByText('founder.test@example.com')).toBeInTheDocument()
    expect(screen.queryByText('History')).not.toBeInTheDocument()
  })

  it('opens the dropdown on click and lists the destinations plus sign out', () => {
    render(<AccountMenu currentUser={user} onNavigate={vi.fn()} onSignOut={vi.fn()} />)
    fireEvent.click(screen.getByTitle('Signed in as founder.test@example.com'))

    expect(screen.getByText('History')).toBeInTheDocument()
    expect(screen.getByText('Compare ideas')).toBeInTheDocument()
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.getByText('Sign out')).toBeInTheDocument()
    expect(screen.queryByText('Platform health')).not.toBeInTheDocument()
  })

  it('only shows Platform health for admins', () => {
    render(<AccountMenu currentUser={admin} onNavigate={vi.fn()} onSignOut={vi.fn()} />)
    fireEvent.click(screen.getByTitle('Signed in as admin.test@example.com'))
    expect(screen.getByText('Platform health')).toBeInTheDocument()
  })

  it('navigates and closes the menu when an item is clicked', () => {
    const onNavigate = vi.fn()
    render(<AccountMenu currentUser={user} onNavigate={onNavigate} onSignOut={vi.fn()} />)
    fireEvent.click(screen.getByTitle('Signed in as founder.test@example.com'))
    fireEvent.click(screen.getByText('Dashboard'))

    expect(onNavigate).toHaveBeenCalledWith('analytics')
    expect(screen.queryByText('Dashboard')).not.toBeInTheDocument()
  })

  it('signs out and closes the menu when Sign out is clicked', () => {
    const onSignOut = vi.fn()
    render(<AccountMenu currentUser={user} onNavigate={vi.fn()} onSignOut={onSignOut} />)
    fireEvent.click(screen.getByTitle('Signed in as founder.test@example.com'))
    fireEvent.click(screen.getByText('Sign out'))

    expect(onSignOut).toHaveBeenCalled()
    expect(screen.queryByText('Sign out')).not.toBeInTheDocument()
  })

  it('closes the menu when clicking outside of it', () => {
    render(
      <div>
        <div data-testid="outside">Outside</div>
        <AccountMenu currentUser={user} onNavigate={vi.fn()} onSignOut={vi.fn()} />
      </div>
    )
    fireEvent.click(screen.getByTitle('Signed in as founder.test@example.com'))
    expect(screen.getByText('History')).toBeInTheDocument()

    fireEvent.mouseDown(screen.getByTestId('outside'))
    expect(screen.queryByText('History')).not.toBeInTheDocument()
  })

  it('closes the menu on Escape', () => {
    render(<AccountMenu currentUser={user} onNavigate={vi.fn()} onSignOut={vi.fn()} />)
    fireEvent.click(screen.getByTitle('Signed in as founder.test@example.com'))
    expect(screen.getByText('History')).toBeInTheDocument()

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByText('History')).not.toBeInTheDocument()
  })
})
