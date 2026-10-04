import session from 'express-session'
import MongoStore from 'connect-mongo'
import mongoose from 'mongoose'
import { env } from './env.js'

export const sessionCookieName = 'paperdesk.sid'

export function sessionMiddleware() {
  return session({
    name: sessionCookieName,
    secret: env.SESSION_SECRET,
    resave: false,
    saveUninitialized: false,
    rolling: false,
    store: MongoStore.create({ clientPromise: Promise.resolve(mongoose.connection.getClient()), dbName: env.MONGODB_DB_NAME, collectionName: 'sessions' }),
    cookie: {
      httpOnly: true,
      sameSite: 'lax',
      secure: 'auto',
      path: '/',
      maxAge: 7 * 24 * 60 * 60 * 1000,
    },
  })
}
