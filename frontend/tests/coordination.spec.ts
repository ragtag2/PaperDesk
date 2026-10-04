import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

async function signIn(page: Page, email = 'sam@paperdesk.test') {
  await page.goto('/login')
  await page.getByLabel('Email address').fill(email)
  await page.getByLabel('Password').fill('password123')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: 'Ticket board.' })).toBeVisible()
}

test('admin manages teams and assigns or removes user membership', async ({ page }) => {
  await signIn(page)
  await page.getByRole('link', { name: 'Teams', exact: true }).click()
  await page.getByRole('button', { name: 'Add team', exact: true }).click()
  let dialog = page.getByRole('dialog')
  await expect(dialog.getByLabel('Team name')).toBeFocused()
  await dialog.getByLabel('Team name').fill('Operations')
  await dialog.getByLabel('Responsibilities').fill('Coordinate facilities and office equipment.')
  await dialog.getByRole('button', { name: 'Add team', exact: true }).click()
  await expect(page.getByRole('row', { name: /Operations/ })).toContainText('Coordinate facilities')
  await page.getByRole('button', { name: 'Edit Operations', exact: true }).click()
  dialog = page.getByRole('dialog')
  await dialog.getByLabel('Responsibilities').fill('Maintain facilities and coordinate office moves.')
  await dialog.getByRole('button', { name: 'Save changes' }).click()
  await page.reload()
  await expect(page.getByRole('row', { name: /Operations/ })).toContainText('coordinate office moves')

  await page.getByRole('link', { name: 'Team members', exact: true }).click()
  await page.getByRole('button', { name: 'Add member', exact: true }).click()
  dialog = page.getByRole('dialog')
  await dialog.getByLabel('Full name').fill('Jordan Lee')
  await dialog.getByLabel('Email address').fill('jordan@paperdesk.test')
  await dialog.getByLabel('Temporary password').fill('password123')
  await dialog.getByLabel('Team', { exact: true }).selectOption({ label: 'Operations' })
  await dialog.getByRole('button', { name: 'Add member', exact: true }).click()
  await expect(page.getByRole('row', { name: /Jordan Lee/ })).toContainText('Operations')
  await page.getByRole('button', { name: 'Edit Jordan Lee', exact: true }).click()
  dialog = page.getByRole('dialog')
  await expect(dialog.getByLabel('Team', { exact: true }).locator('option:checked')).toHaveText('Operations')
  await dialog.getByLabel('Team', { exact: true }).selectOption('')
  await dialog.getByRole('button', { name: 'Save changes' }).click()
  await page.reload()
  await expect(page.getByRole('row', { name: /Jordan Lee/ })).toContainText('No team')
})

test('mobile admin can edit teams and membership with keyboard-accessible forms', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.setViewportSize({ width: 390, height: 844 })
  await signIn(page)
  await page.getByRole('button', { name: 'Open menu' }).click()
  await page.getByRole('link', { name: 'Teams', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Teams.' })).toBeVisible()
  await page.getByRole('button', { name: 'Edit IT', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Team name').fill('IT Operations')
  await dialog.getByLabel('Responsibilities').fill('Maintain networks, devices, and access.')
  await dialog.getByRole('button', { name: 'Save changes' }).click()
  await expect(page.getByRole('heading', { name: 'IT Operations', exact: true })).toBeVisible()
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
  await page.screenshot({ path: 'artifacts/teams-mobile.png', fullPage: true })
  await page.getByRole('button', { name: 'Open menu' }).click()
  await page.getByRole('link', { name: 'Team members', exact: true }).click()
  await page.getByRole('button', { name: 'Edit Ava Morgan', exact: true }).click()
  const memberDialog = page.getByRole('dialog')
  await memberDialog.getByLabel('Team', { exact: true }).selectOption({ label: 'IT Operations' })
  await memberDialog.getByRole('button', { name: 'Save changes' }).click()
  await expect(page.locator('.user-mobile-card').filter({ hasText: 'Ava Morgan' })).toContainText('Team: IT Operations')
  await page.screenshot({ path: 'artifacts/members-mobile.png', fullPage: true })
  await page.getByRole('button', { name: 'Edit Ava Morgan', exact: true }).click()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Edit Ava Morgan', exact: true })).toBeFocused()
})

test('employees see coordination names and delayed analysis preserves unsaved edits', async ({ page }) => {
  await page.clock.install()
  await signIn(page, 'ava@paperdesk.test')
  await expect(page.getByRole('link', { name: 'Teams', exact: true })).toHaveCount(0)
  await page.goto('/teams')
  await expect(page).toHaveURL(/\/tickets$/)
  await page.evaluate(() => {
    const data = JSON.parse(localStorage.getItem('paperdesk_demo_data')!)
    data.tickets.find((ticket: { _id: string }) => ticket._id === 't-1048').coordination = null
    localStorage.setItem('paperdesk_demo_data', JSON.stringify(data))
  })
  await page.goto('/tickets/t-1048')
  const panel = page.getByRole('region', { name: "Who's involved?" })
  await expect(panel.getByText('No analysis available yet.')).toBeVisible()
  await page.getByRole('button', { name: 'Edit', exact: true }).click()
  await page.getByLabel('Title', { exact: true }).fill('My unsaved title')
  await page.evaluate(() => {
    const data = JSON.parse(localStorage.getItem('paperdesk_demo_data')!)
    data.tickets.find((ticket: { _id: string }) => ticket._id === 't-1048').coordination = {
      summary: 'The connection failure affects design work.',
      relevantTeams: [{ teamId: 'team-it', reason: 'IT maintains the office network.' }],
      stakeholderUserIds: ['u-mia', 'u-sam'], analyzedAt: new Date().toISOString(),
    }
    localStorage.setItem('paperdesk_demo_data', JSON.stringify(data))
  })
  await page.clock.runFor(5000)
  await expect(panel.getByText('The connection failure affects design work.')).toBeVisible()
  await expect(panel.getByText('IT', { exact: true })).toBeVisible()
  await expect(panel.getByText('Mia Chen', { exact: true })).toBeVisible()
  await expect(panel.getByText('Sam Rivera', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Title', { exact: true })).toHaveValue('My unsaved title')
  await expect(page.getByRole('heading', { name: 'Move it along' })).toHaveCount(0)
})

test('coordination refresh reads saved results and surfaces a recoverable error', async ({ page }) => {
  await signIn(page, 'mia@paperdesk.test')
  await page.goto('/tickets/t-1048')
  const panel = page.getByRole('region', { name: "Who's involved?" })
  await expect(panel.getByText('Mia Chen', { exact: true })).toBeVisible()
  await page.getByLabel('Status', { exact: true }).selectOption('resolved')
  const saved = await page.evaluate(() => {
    const value = localStorage.getItem('paperdesk_demo_data')!
    const data = JSON.parse(value)
    data.tickets = data.tickets.filter((ticket: { _id: string }) => ticket._id !== 't-1048')
    localStorage.setItem('paperdesk_demo_data', JSON.stringify(data))
    return value
  })
  await panel.getByRole('button', { name: 'Refresh coordination' }).click()
  await expect(panel.getByRole('alert')).toContainText('Ticket not found.')
  await page.evaluate((value) => {
    const data = JSON.parse(value)
    data.tickets.find((ticket: { _id: string }) => ticket._id === 't-1048').coordination.summary = 'A new saved analysis is available.'
    localStorage.setItem('paperdesk_demo_data', JSON.stringify(data))
  }, saved)
  await panel.getByRole('button', { name: 'Refresh coordination' }).click()
  await expect(panel.getByRole('alert')).toHaveCount(0)
  await expect(panel.getByText('A new saved analysis is available.')).toBeVisible()
  await expect(page.getByLabel('Status', { exact: true })).toHaveValue('resolved')
})
