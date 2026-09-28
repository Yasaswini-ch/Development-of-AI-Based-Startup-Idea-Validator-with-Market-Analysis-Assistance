import { useEffect, useState } from 'react'

const TYPE_MS = 45
const ERASE_MS = 20
const HOLD_MS = 1400
const PAUSE_MS = 500

// Purely decorative for the landing page's "watch it validate an idea"
// demo - cycles through a fixed list of example ideas, typing each one out,
// holding, then erasing before moving to the next. No backend call involved.
export default function useTypewriter(items) {
  const [index, setIndex] = useState(0)
  const [text, setText] = useState('')
  const [phase, setPhase] = useState('typing')

  useEffect(() => {
    const current = items[index % items.length]
    let timeout

    if (phase === 'typing') {
      if (text.length < current.length) {
        timeout = setTimeout(() => setText(current.slice(0, text.length + 1)), TYPE_MS)
      } else {
        timeout = setTimeout(() => setPhase('holding'), HOLD_MS)
      }
    } else if (phase === 'holding') {
      timeout = setTimeout(() => setPhase('erasing'), HOLD_MS)
    } else {
      if (text.length > 0) {
        timeout = setTimeout(() => setText(text.slice(0, -1)), ERASE_MS)
      } else {
        timeout = setTimeout(() => {
          setIndex((i) => (i + 1) % items.length)
          setPhase('typing')
        }, PAUSE_MS)
      }
    }

    return () => clearTimeout(timeout)
  }, [text, phase, index, items])

  return { text, settled: phase === 'holding', index: index % items.length }
}
