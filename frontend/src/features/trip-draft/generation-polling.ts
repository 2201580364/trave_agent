import type { GenerationIntent } from '@/entities/planning/types'
import { errorMessageForCode } from '@/shared/api/client'

export interface GenerationPollOptions {
  fetchStatus: (intentId: string) => Promise<GenerationIntent>
  sleep?: (milliseconds: number) => Promise<void>
  now?: () => number
  intervalMilliseconds?: number
  timeoutMilliseconds?: number
}

const defaultSleep = (milliseconds: number): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, milliseconds))

export async function waitForGeneration(
  intent: GenerationIntent,
  options: GenerationPollOptions
): Promise<GenerationIntent> {
  const startedAt = (options.now ?? Date.now)()
  const sleep = options.sleep ?? defaultSleep
  const now = options.now ?? Date.now
  const intervalMilliseconds = options.intervalMilliseconds ?? 1500
  const timeoutMilliseconds = options.timeoutMilliseconds ?? 10 * 60 * 1000
  let current = intent

  while (current.status === 'queued' || current.status === 'running') {
    if (now() - startedAt >= timeoutMilliseconds) {
      throw new Error(errorMessageForCode('generation_wait_timeout'))
    }
    await sleep(intervalMilliseconds)
    current = await options.fetchStatus(current.generation_intent_id)
  }
  return current
}
