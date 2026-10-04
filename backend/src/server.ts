import mongoose from 'mongoose'
import { createApp } from './app.js'
import { connectDatabase } from './config/database.js'
import { env } from './config/env.js'
import { TicketModel } from './modules/tickets/ticket.model.js'
import { UserModel } from './modules/users/user.model.js'

async function main() {
  await connectDatabase()
  await Promise.all([UserModel.init(), TicketModel.init()])
  const server = createApp().listen(env.PORT, () => {
    console.log(`Paperdesk API listening on port ${env.PORT}`)
  })
  const stop = () => server.close(() => { void mongoose.disconnect().then(() => process.exit(0)) })
  process.on('SIGINT', stop)
  process.on('SIGTERM', stop)
}

main().catch((error: unknown) => {
  console.error('Could not start Paperdesk API:', error)
  process.exitCode = 1
})
