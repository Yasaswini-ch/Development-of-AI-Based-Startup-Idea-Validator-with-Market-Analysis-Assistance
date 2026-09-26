import { render } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import GoogleSignInButton from '../GoogleSignInButton'

describe('GoogleSignInButton', () => {
  const originalClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID

  afterEach(() => {
    import.meta.env.VITE_GOOGLE_CLIENT_ID = originalClientId
  })

  it('renders nothing when no client ID is configured', () => {
    import.meta.env.VITE_GOOGLE_CLIENT_ID = ''
    const { container } = render(<GoogleSignInButton onCredential={() => {}} />)
    expect(container).toBeEmptyDOMElement()
  })
})
