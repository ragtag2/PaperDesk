import { Router } from 'express'
import { requireAuth } from '../../middleware/requireAuth.js'
import { requireRole } from '../../middleware/requireRole.js'
import { validate } from '../../middleware/validate.js'
import { createTeamSchema, teamsQuerySchema, updateTeamSchema } from './teams.schemas.js'
import { createTeamController, listTeamsController, updateTeamController } from './teams.controller.js'

export const teamsRoutes = Router()
teamsRoutes.use(requireAuth, requireRole('admin'))
teamsRoutes.get('/', validate({ query: teamsQuerySchema }), listTeamsController)
teamsRoutes.post('/', validate({ body: createTeamSchema }), createTeamController)
teamsRoutes.patch('/:id', validate({ body: updateTeamSchema }), updateTeamController)
