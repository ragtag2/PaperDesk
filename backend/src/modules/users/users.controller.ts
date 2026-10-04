import type { RequestHandler } from 'express'
import type { ChangePasswordInput, CreateUserInput, UpdateMeInput, UpdateUserInput, UsersQuery } from './users.schemas.js'
import * as service from './users.service.js'

export const meController: RequestHandler = async (req, res) => {
  res.json(await service.getMe(req.auth!.userId))
}
export const updateMeController: RequestHandler = async (req, res) => {
  res.json(await service.updateMe(req.auth!.userId, req.body as UpdateMeInput))
}
export const changePasswordController: RequestHandler = async (req, res) => {
  await service.changePassword(req.auth!.userId, req.body as ChangePasswordInput)
  res.sendStatus(204)
}
export const listUsersController: RequestHandler = async (req, res) => {
  res.json(await service.listUsers(req.validatedQuery as UsersQuery))
}
export const createUserController: RequestHandler = async (req, res) => {
  res.status(201).json(await service.createUser(req.body as CreateUserInput))
}
export const getUserController: RequestHandler = async (req, res) => {
  res.json(await service.getUser(req.params.id as string))
}
export const updateUserController: RequestHandler = async (req, res) => {
  res.json(await service.updateUser(req.params.id as string, req.auth!.userId, req.body as UpdateUserInput))
}
export const deactivateUserController: RequestHandler = async (req, res) => {
  await service.deactivateUser(req.params.id as string, req.auth!.userId)
  res.sendStatus(204)
}
