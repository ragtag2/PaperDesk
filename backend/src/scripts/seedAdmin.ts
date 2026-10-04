import bcrypt from 'bcryptjs'
import mongoose from 'mongoose'
import { connectDatabase } from '../config/database.js'
import { UserModel } from '../modules/users/user.model.js'

async function main() {
  const name = process.env.ADMIN_NAME?.trim()
  const email = process.env.ADMIN_EMAIL?.trim().toLowerCase()
  const password = process.env.ADMIN_PASSWORD
  if (!name || !email || !password || password.length < 8) {
    throw new Error('Set ADMIN_NAME, ADMIN_EMAIL and ADMIN_PASSWORD (at least 8 characters).')
  }
  await connectDatabase()
  try {
    const existing = await UserModel.findOne({ email })
    if (existing) throw new Error('An account with this email already exists.')
    await UserModel.create({ name, email, passwordHash: await bcrypt.hash(password, 12), role: 'admin', isActive: true })
    console.log('Admin account created.')
  } finally {
    await mongoose.disconnect()
  }
}

main().catch((error: unknown) => { console.error(error); process.exitCode = 1 })
