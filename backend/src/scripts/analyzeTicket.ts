import { randomUUID } from 'node:crypto'
import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import mongoose from 'mongoose'
import { connectDatabase } from '../config/database.js'
import { env } from '../config/env.js'
import { TeamModel } from '../modules/teams/team.model.js'
import { TicketModel } from '../modules/tickets/ticket.model.js'
import { coordinateTicket } from '../modules/tickets/ticketCoordination.js'
import { UserModel } from '../modules/users/user.model.js'
import { objectId } from '../shared/objectId.js'
import { serializeTicket } from '../shared/serialize.js'

function sameIds(actual: string[], expected: string[]) {
  return actual.length === expected.length && [...actual].sort().every((id, index) => id === [...expected].sort()[index])
}

async function main() {
  const args = process.argv.slice(2)
  if (args.length !== 1 || !args[0]) {
    throw new Error('Usage: npm run agent:analyze -- <existing-ticket-id>')
  }
  const ticketId = String(objectId(args[0]))
  if (!env.AGENT_BASE_URL) throw new Error('Set AGENT_BASE_URL in backend/.env and start the Python agent.')

  await connectDatabase()
  try {
    const before = await TicketModel.findById(ticketId).lean()
    if (!before) throw new Error('Ticket not found.')
    const startedAt = new Date()
    const started = performance.now()
    const { result, saved } = await coordinateTicket(ticketId, before.updatedAt)
    if (!saved) throw new Error('The ticket changed during analysis. Its newer result was preserved; rerun the command.')
    const after = await TicketModel.findById(ticketId).lean()
    if (!after?.coordination) throw new Error('The saved coordination result could not be read.')

    const coordination = after.coordination
    const checks = {
      ticketUpdatedAtUnchanged: after.updatedAt.getTime() === before.updatedAt.getTime(),
      freshAnalysis: coordination.analyzedAt.getTime() >= startedAt.getTime(),
      summarySaved: coordination.summary === result.summary,
      selectedTeamsSaved: sameIds(coordination.relevantTeams.map((team) => String(team.teamId)), result.relevantTeams.map((team) => team.teamId)),
      stakeholdersSaved: sameIds(coordination.stakeholderUserIds.map(String), result.stakeholderUserIds),
      reasonsSaved: result.relevantTeams.every((team) => coordination.relevantTeams.some((stored) => String(stored.teamId) === team.teamId && stored.reason === team.reason)),
    }
    if (!Object.values(checks).every(Boolean)) throw new Error('The saved result did not match the completed analysis, or the ticket changed during verification.')

    const personIds = [after.creatorId, ...coordination.stakeholderUserIds, ...(after.assigneeId ? [after.assigneeId] : [])]
    const [people, teams] = await Promise.all([
      UserModel.find({ _id: { $in: personIds } }).select('name').lean(),
      TeamModel.find({ _id: { $in: coordination.relevantTeams.map((team) => team.teamId) } }).select('name').lean(),
    ])
    const display = serializeTicket(
      after,
      new Map(people.map((person) => [String(person._id), person])),
      new Map(teams.map((team) => [String(team._id), team.name])),
    )
    const report = {
      status: 'passed',
      startedAt: startedAt.toISOString(),
      ticketId,
      ticketTitle: after.title,
      agentBaseUrl: env.AGENT_BASE_URL,
      elapsedSeconds: Number(((performance.now() - started) / 1000).toFixed(3)),
      checks,
      coordination: display.coordination,
    }
    const directory = new URL(`../../../agents/runs/analyses/${ticketId}/`, import.meta.url)
    await mkdir(directory, { recursive: true })
    const filename = `${startedAt.toISOString().replace(/[:.]/g, '-')}-${randomUUID().slice(0, 8)}-saved.json`
    const reportUrl = new URL(filename, directory)
    await writeFile(reportUrl, JSON.stringify(report, null, 2) + '\n', 'utf8')
    console.log(JSON.stringify(report, null, 2))
    console.log(`Saved report: ${fileURLToPath(reportUrl)}`)
  } finally {
    await mongoose.disconnect()
  }
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : 'Ticket analysis failed.')
  process.exitCode = 1
})
