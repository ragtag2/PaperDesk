import dns from 'node:dns'
import mongoose from 'mongoose'
import { env } from './env.js'

export async function connectDatabase() {
  if (env.MONGODB_URI.startsWith('mongodb+srv://') && env.MONGODB_DNS_SERVERS) {
    dns.setServers(env.MONGODB_DNS_SERVERS.split(',').map((server) => server.trim()).filter(Boolean))
  }
  await mongoose.connect(env.MONGODB_URI, { dbName: env.MONGODB_DB_NAME })
}
