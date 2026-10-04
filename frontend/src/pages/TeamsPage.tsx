import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Check, Pencil, Plus, UserPlus, X } from 'lucide-react'
import { api } from '../api/client'
import type { Team } from '../api/types'
import { Alert, Button, EmptyState, Field, LoadingScreen, PageHeading, TextAreaField } from '../components/Ui'
import { TeamMembersDialog } from '../components/TeamMembersDialog'

function TeamDialog({ team, onClose, onSaved }: { team: Team | null; onClose: () => void; onSaved: () => void }) {
  const ref = useRef<HTMLDialogElement>(null)
  const [name, setName] = useState(team?.name ?? '')
  const [responsibilities, setResponsibilities] = useState(team?.responsibilities ?? '')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const dialog = ref.current
    dialog?.showModal()
    dialog?.querySelector<HTMLInputElement>('#team-name')?.focus()
    return () => { dialog?.close(); trigger?.focus() }
  }, [])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError('')
    const input = { name: name.trim(), responsibilities: responsibilities.trim() }
    if (!input.name || !input.responsibilities) { setError('Enter a team name and its responsibilities.'); return }
    setBusy(true)
    try {
      if (team) await api.teams.update(team._id, input)
      else await api.teams.create(input)
      onSaved()
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not save this team.') }
    finally { setBusy(false) }
  }

  return <dialog ref={ref} className="dialog user-dialog" aria-labelledby="team-dialog-title" onCancel={onClose} onClick={(event) => { if (event.target === ref.current) onClose() }}>
    <div className="dialog-content">
      <button type="button" className="dialog-close icon-button" onClick={onClose} aria-label="Close dialog"><X size={20} /></button>
      <span className="section-kicker">TEAM MANAGEMENT</span>
      <h2 id="team-dialog-title">{team ? 'Edit team' : 'Add a team'}<span className="heading-period">.</span></h2>
      <p>Describe what this team handles so relevant incidents reach the right people.</p>
      {error && <Alert>{error}</Alert>}
      <form onSubmit={submit}>
        <Field id="team-name" label="Team name" value={name} onChange={(event) => setName(event.target.value)} maxLength={120} required />
        <TextAreaField id="team-responsibilities" label="Responsibilities" hint="For example: maintain office networks, devices, and application access." rows={5} value={responsibilities} onChange={(event) => setResponsibilities(event.target.value)} maxLength={5000} required />
        <div className="dialog-actions">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" busy={busy}><Check size={18} /> {team ? 'Save changes' : 'Add team'}</Button>
        </div>
      </form>
    </div>
  </dialog>
}

export function TeamsPage() {
  const [teams, setTeams] = useState<Team[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [refresh, setRefresh] = useState(0)
  const [editing, setEditing] = useState<Team | 'new' | null>(null)
  const [addingMembers, setAddingMembers] = useState<Team | null>(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    api.teams.list()
      .then((items) => { if (active) { setTeams(items); setError('') } })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : 'Could not load teams.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [refresh])

  function saved() {
    setNotice(editing === 'new' ? 'Team added.' : 'Team updated.')
    setEditing(null); setRefresh((value) => value + 1)
  }

  return <div className="teams-page">
    <PageHeading eyebrow="INCIDENT COORDINATION" title="Teams" description="Who handles what, in one place." action={<Button type="button" onClick={() => setEditing('new')}><Plus size={19} /> Add team</Button>} />
    {notice && <Alert kind="success">{notice}</Alert>}
    <section className="ticket-section" aria-labelledby="teams-heading">
      <div className="section-top"><div><span className="section-kicker">YOUR TEAMS</span><h2 id="teams-heading">Directory <span className="section-count">{teams.length}</span></h2></div></div>
      {error && <div className="teams-feedback"><Alert>{error}</Alert><Button type="button" variant="secondary" onClick={() => setRefresh((value) => value + 1)}>Try again</Button></div>}
      {loading ? <LoadingScreen label="Gathering the teams…" /> : !error && (teams.length ? <>
        <div className="ticket-table-wrap"><table className="ticket-table teams-table">
          <thead><tr><th>Team</th><th>Responsibilities</th><th>Actions</th></tr></thead>
          <tbody>{teams.map((team) => <tr key={team._id}>
            <td><strong>{team.name}</strong></td><td><p className="team-responsibilities">{team.responsibilities}</p></td>
            <td><div className="table-actions"><button type="button" className="icon-button" onClick={() => setEditing(team)} aria-label={`Edit ${team.name}`} title="Edit team"><Pencil size={18} /></button><button type="button" className="icon-button" onClick={() => setAddingMembers(team)} aria-label={`Add members to ${team.name}`} title="Add members"><UserPlus size={18} /></button></div></td>
          </tr>)}</tbody>
        </table></div>
        <div className="user-cards">{teams.map((team) => <article className="user-mobile-card" key={team._id}>
          <div className="detail-section-top"><h3>{team.name}</h3><button type="button" className="icon-button" onClick={() => setEditing(team)} aria-label={`Edit ${team.name}`}><Pencil size={18} /></button></div>
          <p className="team-responsibilities">{team.responsibilities}</p>
          <Button type="button" variant="quiet" onClick={() => setAddingMembers(team)} aria-label={`Add members to ${team.name}`}><UserPlus size={18} /> Add members</Button>
        </article>)}</div>
      </> : <EmptyState title="No teams yet" description="Add a team and describe its responsibilities, then choose its members." />)}
    </section>
    {editing && <TeamDialog key={editing === 'new' ? 'new' : editing._id} team={editing === 'new' ? null : editing} onClose={() => setEditing(null)} onSaved={saved} />}
    {addingMembers && <TeamMembersDialog key={addingMembers._id} team={addingMembers} onClose={() => setAddingMembers(null)} onSaved={(count) => {
      setNotice(`${count} ${count === 1 ? 'member' : 'members'} added to ${addingMembers.name}.`)
      setAddingMembers(null)
    }} />}
  </div>
}
