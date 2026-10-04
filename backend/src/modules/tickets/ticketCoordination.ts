import { env } from '../../config/env.js'
import { analyzeTicket } from '../../integrations/agent.client.js'
import { objectId } from '../../shared/objectId.js'
import { TicketModel, type TicketRecord } from './ticket.model.js'
import { notifyNewStakeholders } from '../notifications/notifications.service.js'

export async function coordinateTicket(ticketId: string, updatedAt: Date) {
  const result = await analyzeTicket(ticketId)
  const coordination = {
    summary: result.summary,
    relevantTeams: result.relevantTeams.map((team) => ({ teamId: objectId(team.teamId), reason: team.reason })),
    stakeholderUserIds: result.stakeholderUserIds.map(objectId),
    analyzedAt: new Date(),
  }
  // The previous value comes from the same atomic save, even for overlapping calls.
  const previous = await TicketModel.findOneAndUpdate({ _id: objectId(ticketId), updatedAt }, {
    $set: {
      coordination,
    },
  }, { runValidators: true, timestamps: false, returnDocument: 'before' }).lean()
  if (previous) {
    try { await notifyNewStakeholders(previous, { ...previous, coordination }) }
    catch { console.warn(`Involvement notifications failed for saved ticket ${ticketId}.`) }
  }
  return { result, saved: previous !== null }
}

export function scheduleTicketCoordination(ticket: Pick<TicketRecord, '_id' | 'updatedAt'>) {
  if (!env.AGENT_BASE_URL) return
  const ticketId = String(ticket._id)
  void coordinateTicket(ticketId, ticket.updatedAt).catch(() => {
    console.warn(`Incident coordination failed for ticket ${ticketId}; the previous result was retained.`)
  })
}
