import { mongo } from 'mongoose'
import { HttpError } from '../../shared/httpError.js'
import { objectId } from '../../shared/objectId.js'
import { pageResult } from '../../shared/pagination.js'
import { TicketModel, type TicketRecord } from '../tickets/ticket.model.js'
import { visibleFilter, type Actor } from '../tickets/ticketPermissions.js'
import { UserModel } from '../users/user.model.js'
import { NotificationModel, type NotificationRecord, type NotificationType } from './notification.model.js'
import type { NotificationsQuery } from './notifications.schemas.js'

async function enrich(notifications: NotificationRecord[], actor: Actor) {
  const tickets = await TicketModel.find({
    _id: { $in: notifications.map((item) => item.ticketId) }, ...visibleFilter(actor),
  }).select('_id').lean()
  const available = new Set(tickets.map((ticket) => String(ticket._id)))
  return notifications.map((item) => ({
    _id: String(item._id), userId: String(item.userId), ticketId: String(item.ticketId),
    ticketTitle: item.ticketTitle, type: item.type, createdAt: item.createdAt.toISOString(),
    readAt: item.readAt?.toISOString() ?? null, ticketAvailable: available.has(String(item.ticketId)),
  }))
}

export async function listNotifications(actor: Actor, query: NotificationsQuery) {
  const userId = objectId(actor.userId)
  const filter = { userId, ...(query.unread === undefined ? {} : { readAt: query.unread ? null : { $ne: null } }) }
  const [items, total, unreadCount] = await Promise.all([
    NotificationModel.find(filter).sort({ createdAt: -1, _id: -1 }).skip((query.page - 1) * query.limit).limit(query.limit).lean(),
    NotificationModel.countDocuments(filter),
    NotificationModel.countDocuments({ userId, readAt: null }),
  ])
  return { ...pageResult(await enrich(items, actor), query.page, query.limit, total), unreadCount }
}

export async function markNotificationRead(id: string, actor: Actor) {
  const filter = { _id: objectId(id), userId: objectId(actor.userId) }
  const item = await NotificationModel.findOneAndUpdate({ ...filter, readAt: null }, {
    $set: { readAt: new Date() },
  }, { returnDocument: 'after' }).lean() ?? await NotificationModel.findOne(filter).lean()
  if (!item) throw new HttpError(404, 'Notification not found.')
  return (await enrich([item], actor))[0]
}

export async function markAllNotificationsRead(actor: Actor) {
  const now = new Date()
  await NotificationModel.updateMany({ userId: objectId(actor.userId), readAt: null, createdAt: { $lte: now } }, {
    $set: { readAt: now },
  })
}

async function createNotifications(ticket: TicketRecord, recipients: string[], type: NotificationType, eventKey: string) {
  if (!recipients.length) return
  const users = await UserModel.find({ _id: { $in: [...new Set(recipients)].map(objectId) }, isActive: true }).select('_id').lean()
  if (!users.length) return
  const now = new Date()
  try {
    await NotificationModel.bulkWrite(users.map((user) => ({
      updateOne: {
        filter: { userId: user._id, ticketId: ticket._id, type, eventKey },
        update: { $setOnInsert: { ticketTitle: ticket.title, createdAt: now, readAt: null } },
        upsert: true,
      },
    })), { ordered: false })
  } catch (error) {
    // Concurrent saves can attempt the same indexed event; an existing alert wins.
    if (!(error instanceof mongo.MongoBulkWriteError)) throw error
    const writeErrors = Array.isArray(error.writeErrors) ? error.writeErrors : [error.writeErrors]
    if (!writeErrors.length || !writeErrors.every((item) => item.code === 11000) || error.result.getWriteConcernError()) throw error
  }
}

export async function notifyNewStakeholders(previous: TicketRecord, current: TicketRecord) {
  const existing = new Set(previous.coordination?.stakeholderUserIds.map(String) ?? [])
  const added = (current.coordination?.stakeholderUserIds.map(String) ?? []).filter((id) => !existing.has(id))
  await createNotifications(current, added, 'ticket_involvement', current.updatedAt.toISOString())
}

export async function notifyTicketResolved(previous: TicketRecord, current: TicketRecord) {
  if (previous.status === 'resolved' || current.status !== 'resolved') return
  await createNotifications(current, [String(current.creatorId), ...(current.coordination?.stakeholderUserIds.map(String) ?? [])],
    'ticket_resolved', previous.updatedAt.toISOString())
}
