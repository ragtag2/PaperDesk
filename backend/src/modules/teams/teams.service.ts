import { TeamModel } from './team.model.js'
import type { CreateTeamInput, UpdateTeamInput } from './teams.schemas.js'
import { HttpError } from '../../shared/httpError.js'
import { objectId } from '../../shared/objectId.js'
import { serializeTeam } from '../../shared/serialize.js'

export async function listTeams() {
  const teams = await TeamModel.find().sort({ name: 1, _id: 1 }).lean()
  return teams.map(serializeTeam)
}

export async function createTeam(input: CreateTeamInput) {
  return serializeTeam(await TeamModel.create(input))
}

export async function updateTeam(id: string, patch: UpdateTeamInput) {
  const team = await TeamModel.findByIdAndUpdate(objectId(id), patch, {
    returnDocument: 'after', runValidators: true,
  }).lean()
  if (!team) throw new HttpError(404, 'Team not found.')
  return serializeTeam(team)
}

export async function resolveTeamId(id: string | null) {
  if (id === null) return null
  const teamId = objectId(id)
  if (!(await TeamModel.exists({ _id: teamId }))) throw new HttpError(400, 'Team not found.')
  return teamId
}
