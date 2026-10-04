import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Check, Pencil, Plus, UserX, Users, X } from 'lucide-react'
import { api } from '../api/client'
import type { NewUser, Page, Role, Team, User } from '../api/types'
import { useAuth } from '../app/AuthContext'
import { Alert, Badge, Button, ConfirmDialog, EmptyState, Field, LoadingScreen, PageHeading, Pagination, SelectField } from '../components/Ui'
import { shortDate } from '../features/tickets'

const pageSize = 10

function UserDialog({ user, teams, selfId, onClose, onSaved }: { user: User | null; teams: Team[]; selfId?: string; onClose: () => void; onSaved: () => void }) {
  const ref = useRef<HTMLDialogElement>(null)
  const [name, setName] = useState(user?.name ?? '')
  const [email, setEmail] = useState(user?.email ?? '')
  const [role, setRole] = useState<Role>(user?.role ?? 'employee')
  const [password, setPassword] = useState('')
  const [teamId, setTeamId] = useState(user?.teamId ?? '')
  const [isActive, setIsActive] = useState(user?.isActive ?? true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const dialog = ref.current
    dialog?.showModal()
    return () => { dialog?.close(); trigger?.focus() }
  }, [])
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError('')
    if (!user && password.length < 8) { setError('Use at least 8 characters for the password.'); return }
    setBusy(true)
    try {
      if (user) await api.users.update(user._id, { name: name.trim(), email: email.trim(), role, isActive, teamId: teamId || null })
      else await api.users.create({ name: name.trim(), email: email.trim(), role, password, teamId: teamId || null } satisfies NewUser)
      onSaved()
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not save this team member.') }
    finally { setBusy(false) }
  }
  return <dialog ref={ref} className="dialog user-dialog" aria-labelledby="user-dialog-title" onCancel={onClose} onClick={(event) => { if (event.target === ref.current) onClose() }}><div className="dialog-content"><button type="button" className="dialog-close icon-button" onClick={onClose} aria-label="Close dialog"><X size={20} /></button><span className="section-kicker">TEAM MANAGEMENT</span><h2 id="user-dialog-title">{user ? 'Edit team member' : 'Add a teammate'}<span className="heading-period">.</span></h2><p>{user ? 'Update their details and workspace access.' : 'Give someone their place in the workspace.'}</p>{error && <Alert>{error}</Alert>}<form onSubmit={submit} className="user-form"><Field id="user-name" label="Full name" autoComplete="name" value={name} onChange={(event) => setName(event.target.value)} required /><Field id="user-email" label="Email address" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />{!user && <Field id="user-password" label="Temporary password" type="password" minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} required />}<SelectField id="user-role" label="Role" value={role} disabled={user?._id === selfId} onChange={(event) => setRole(event.target.value as Role)}><option value="employee">Employee</option><option value="support">Support</option><option value="admin">Admin</option></SelectField><SelectField id="user-team" label="Team" value={teamId} onChange={(event) => setTeamId(event.target.value)}><option value="">No team</option>{teams.map((team) => <option key={team._id} value={team._id}>{team.name}</option>)}</SelectField>{user && <label className="checkbox-row"><input type="checkbox" checked={isActive} disabled={user._id === selfId} onChange={(event) => setIsActive(event.target.checked)} /> Account is active</label>}{user?._id === selfId && <p className="field-hint">Your own role and account status are locked here.</p>}<div className="dialog-actions"><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" busy={busy}><Check size={18} /> {user ? 'Save changes' : 'Add member'}</Button></div></form></div></dialog>
}

export function UsersPage() {
  const { user: me } = useAuth()
  const [result, setResult] = useState<Page<User> | null>(null)
  const [teams, setTeams] = useState<Team[]>([])
  const [page, setPage] = useState(1)
  const [role, setRole] = useState<Role | ''>('')
  const [active, setActive] = useState<'' | 'true' | 'false'>('')
  const [teamFilter, setTeamFilter] = useState('')
  const [refresh, setRefresh] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState<User | null | 'new'>(null)
  const [deactivating, setDeactivating] = useState<User | null>(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    let mounted = true
    Promise.all([api.users.list({ page, limit: pageSize, role, isActive: active, teamId: teamFilter }), api.teams.list()])
      .then(([data, teamList]) => { if (mounted) { setResult(data); setTeams(teamList); setError('') } })
      .catch((reason) => { if (mounted) setError(reason instanceof Error ? reason.message : 'Could not load team members.') })
      .finally(() => { if (mounted) setLoading(false) })
    return () => { mounted = false }
  }, [page, role, active, teamFilter, refresh])

  function teamName(person: User) { return teams.find((team) => team._id === person.teamId)?.name ?? 'No team' }

  function reload(message?: string) { setEditing(null); setDeactivating(null); if (message) setNotice(message); setLoading(true); setRefresh((value) => value + 1) }
  async function deactivate() {
    if (!deactivating) return
    setBusy(true); setError('')
    try { await api.users.deactivate(deactivating._id); reload(`${deactivating.name}'s account has been deactivated.`) }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not deactivate this account.'); setDeactivating(null) }
    finally { setBusy(false) }
  }

  return <div className="users-page"><PageHeading eyebrow="PEOPLE & PERMISSIONS" title="Team members" description="The people behind every request and resolution." action={<Button type="button" onClick={() => setEditing('new')}><Plus size={19} /> Add member</Button>} /><div className="team-intro"><span className="team-intro-icon"><Users size={25} /></span><div><strong>A place for everyone</strong><p>Invite teammates, manage roles, and keep access current.</p></div><span className="team-intro-doodle" aria-hidden="true">↝</span></div><section className="ticket-section users-section" aria-labelledby="users-heading"><div className="section-top"><div><span className="section-kicker">YOUR PEOPLE</span><h2 id="users-heading">Members <span className="section-count">{result?.total ?? 0}</span></h2></div></div><div className="filter-bar"><span className="filter-title">Show</span><label className="sr-only" htmlFor="user-role-filter">Role</label><select id="user-role-filter" value={role} onChange={(event) => { setRole(event.target.value as Role | ''); setPage(1); setLoading(true) }}><option value="">All roles</option><option value="employee">Employee</option><option value="support">Support</option><option value="admin">Admin</option></select><label className="sr-only" htmlFor="user-active-filter">Account status</label><select id="user-active-filter" value={active} onChange={(event) => { setActive(event.target.value as '' | 'true' | 'false'); setPage(1); setLoading(true) }}><option value="">Any status</option><option value="true">Active</option><option value="false">Inactive</option></select><label className="sr-only" htmlFor="user-team-filter">Team</label><select id="user-team-filter" value={teamFilter} onChange={(event) => { setTeamFilter(event.target.value); setPage(1); setLoading(true) }}><option value="">All teams</option><option value="none">No team</option>{teams.map((team) => <option key={team._id} value={team._id}>{team.name}</option>)}</select></div>{error && <Alert>{error}</Alert>}{notice && <Alert kind="success">{notice}</Alert>}{loading ? <LoadingScreen label="Gathering the team…" /> : result?.items.length ? <><div className="ticket-table-wrap"><table className="ticket-table users-table"><thead><tr><th>Member</th><th>Role</th><th>Team</th><th>Status</th><th>Joined</th><th>Actions</th></tr></thead><tbody>{result.items.map((person) => <tr key={person._id}><td><div className="user-cell"><span className="avatar avatar-small">{person.name.split(' ').map((part) => part[0]).slice(0, 2).join('').toUpperCase()}</span><span><strong>{person.name}</strong><small>{person.email}</small></span></div></td><td><Badge value={person.role} kind="role" /></td><td className="membership-cell">{teamName(person)}</td><td><span className={`active-label ${person.isActive ? '' : 'inactive'}`}><span />{person.isActive ? 'Active' : 'Inactive'}</span></td><td className="date-cell">{shortDate(person.createdAt)}</td><td><div className="table-actions"><button type="button" className="icon-button" onClick={() => setEditing(person)} aria-label={`Edit ${person.name}`} title="Edit"><Pencil size={17} /></button>{person.isActive && person._id !== me?._id && <button type="button" className="icon-button" onClick={() => setDeactivating(person)} aria-label={`Deactivate ${person.name}`} title="Deactivate"><UserX size={18} /></button>}</div></td></tr>)}</tbody></table></div><div className="user-cards">{result.items.map((person) => <div className="user-mobile-card" key={person._id}><div className="user-cell"><span className="avatar avatar-small">{person.name.split(' ').map((part) => part[0]).slice(0, 2).join('').toUpperCase()}</span><span><strong>{person.name}</strong><small>{person.email}</small></span></div><p className="member-team">Team: {teamName(person)}</p><div className="user-mobile-bottom"><Badge value={person.role} kind="role" /><span>{person.isActive ? 'Active' : 'Inactive'}</span><button type="button" className="icon-button" onClick={() => setEditing(person)} aria-label={`Edit ${person.name}`}><Pencil size={17} /></button>{person.isActive && person._id !== me?._id && <button type="button" className="icon-button" onClick={() => setDeactivating(person)} aria-label={`Deactivate ${person.name}`}><UserX size={18} /></button>}</div></div>)}</div><Pagination page={result.page} limit={result.limit} total={result.total} onPage={(value) => { setPage(value); setLoading(true) }} /></> : !error && <EmptyState title="No teammates found" description="Try another filter or invite a new member." action={<Button type="button" onClick={() => setEditing('new')}><Plus size={18} /> Add member</Button>} />}</section>{editing && <UserDialog key={editing === 'new' ? 'new' : editing._id} user={editing === 'new' ? null : editing} teams={teams} selfId={me?._id} onClose={() => setEditing(null)} onSaved={() => reload(editing === 'new' ? 'Teammate added.' : 'Team member updated.')} />}{deactivating && <ConfirmDialog title={`Deactivate ${deactivating.name}?`} description="They will no longer be able to sign in. Their record and past tickets remain in the workspace." confirmLabel="Deactivate" danger busy={busy} onConfirm={deactivate} onClose={() => setDeactivating(null)} />}</div>
}
