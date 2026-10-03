import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import HeroOllie from '../HeroOllie'

describe('HeroOllie', () => {
  it('says hi on hover and stops when the pointer leaves', () => {
    render(<HeroOllie />)
    const ollie = screen.getByLabelText('Ollie says hi')
    expect(screen.queryByText("Hi, I'm Ollie!")).toBeNull()
    fireEvent.mouseEnter(ollie)
    expect(screen.getByText("Hi, I'm Ollie!")).toBeInTheDocument()
    fireEvent.mouseLeave(ollie)
    expect(screen.queryByText("Hi, I'm Ollie!")).toBeNull()
  })

  it('also shows on keyboard focus, and a tap keeps it open', () => {
    render(<HeroOllie />)
    const ollie = screen.getByLabelText('Ollie says hi')
    fireEvent.focus(ollie)
    expect(screen.getByText("Hi, I'm Ollie!")).toBeInTheDocument()
    fireEvent.blur(ollie)
    expect(screen.queryByText("Hi, I'm Ollie!")).toBeNull()
    fireEvent.click(ollie)
    fireEvent.mouseLeave(ollie)
    expect(screen.getByText("Hi, I'm Ollie!")).toBeInTheDocument()
  })
})
