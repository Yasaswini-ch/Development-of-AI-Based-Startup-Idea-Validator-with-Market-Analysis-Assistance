import { useEffect, useState } from 'react'

const STEPS = [
  'SEARCHING WEB...',
  'CROSS-CHECKING SOURCES...',
  'AGENT REASONING...',
  'FINALIZING SUMMARY...',
]

export default function useLoadingSteps(isActive, intervalMs = 1600) {
  const [stepIndex, setStepIndex] = useState(0)

  useEffect(() => {
    if (!isActive) {
      setStepIndex(0)
      return
    }
    const id = setInterval(() => {
      setStepIndex((i) => Math.min(i + 1, STEPS.length - 1))
    }, intervalMs)
    return () => clearInterval(id)
  }, [isActive, intervalMs])

  return STEPS[stepIndex]
}
