import type { RequestHandler } from 'express'
import type { CreateTeamInput, UpdateTeamInput } from './teams.schemas.js'
import * as service from './teams.service.js'

export const listTeamsController: RequestHandler = async (_req, res) => {
  res.json(await service.listTeams())
}
export const createTeamController: RequestHandler = async (req, res) => {
  res.status(201).json(await service.createTeam(req.body as CreateTeamInput))
}
export const updateTeamController: RequestHandler = async (req, res) => {
  res.json(await service.updateTeam(req.params.id as string, req.body as UpdateTeamInput))
}
