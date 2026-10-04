import { z } from 'zod'
import { env } from '../config/env.js'
import { objectIdSchema } from '../shared/objectId.js'

const coordinationResultSchema = z.strictObject({
  ticketId: objectIdSchema,
  summary: z.string().trim().min(1),
  relevantTeams: z.array(z.strictObject({
    teamId: objectIdSchema,
    reason: z.string().trim().min(1),
  })),
  stakeholderUserIds: z.array(objectIdSchema),
})

export type CoordinationResult = z.infer<typeof coordinationResultSchema>

export async function analyzeTicket(ticketId: string): Promise<CoordinationResult> {
  if (!env.AGENT_BASE_URL) throw new Error('AGENT_BASE_URL is not configured.')
  const response = await fetch(`${env.AGENT_BASE_URL.replace(/\/+$/, '')}/analyze-ticket`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticketId }),
    signal: AbortSignal.timeout(60_000),
  })
  if (!response.ok) throw new Error(`Agent analysis returned HTTP ${response.status}.`)
  const result = coordinationResultSchema.parse(await response.json())
  if (result.ticketId.toLowerCase() !== ticketId.toLowerCase()) {
    throw new Error('The agent returned a different ticket ID.')
  }
  return result
}
