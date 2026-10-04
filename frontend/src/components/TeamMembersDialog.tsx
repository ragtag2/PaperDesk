import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { UserPlus, X } from 'lucide-react'
import { api } from '../api/client'
import type { Page, Team, User } from '../api/types'
import { Alert, Badge, Button, LoadingScreen, Pagination } from './Ui'

export function TeamMembersDialog({ team, onClose, onSaved }: {
  team: Team
  onClose: () => void
  onSaved: (count: number) => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const [result, setResult] = useState<Page<User> | null>(null)
  const [page, setPage] = useState(1)
  const [refresh, setRefresh] = useState(0)
  const [selected, setSelected] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const addedCount = useRef(0)

  useEffect(() => {
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const dialog = ref.current
    dialog?.showModal()
    return () => { dialog?.close(); trigger?.focus() }
  }, [])

  useEffect(() => {
    let active = true
    setLoading(true); setResult(null)
    api.users.list({ page, limit: 10, isActive: 'true', teamId: 'none' })
      .then((items) => { if (active) setResult(items) })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : 'Could not load available members.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [page, refresh])

  function toggle(person: User) {
    setSelected((current) => current.some((item) => item._id === person._id)
      ? current.filter((item) => item._id !== person._id) : [...current, person])
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selected.length || busy) return
    setBusy(true); setError('')
    const results = await Promise.allSettled(selected.map((person) => api.users.update(person._id, { teamId: team._id })))
    const failed = selected.filter((_, index) => results[index]?.status === 'rejected')
    addedCount.current += selected.length - failed.length
    setBusy(false)
    if (!failed.length) { onSaved(addedCount.current); return }
    setSelected(failed)
    const failure = results.find((item) => item.status === 'rejected')
    const message = failure?.status === 'rejected' && failure.reason instanceof Error ? failure.reason.message : 'Please try again.'
    setError(`${addedCount.current ? `${addedCount.current} added. ` : ''}Could not add ${failed.map((person) => person.name).join(', ')}. ${message}`)
    setPage(1); setRefresh((value) => value + 1)
  }

  function close() { if (!busy) onClose() }

  return <dialog ref={ref} className="dialog user-dialog" aria-labelledby="team-members-title"
    onCancel={(event) => { event.preventDefault(); close() }} onClick={(event) => { if (event.target === ref.current) close() }}>
    <div className="dialog-content">
      <button type="button" className="dialog-close icon-button" onClick={close} disabled={busy} aria-label="Close dialog"><X size={20} /></button>
      <span className="section-kicker">TEAM MEMBERSHIP</span>
      <h2 id="team-members-title">Add members to {team.name}<span className="heading-period">.</span></h2>
      <p>Choose active people who don't belong to a team.</p>
      {error && <Alert>{error}</Alert>}
      {!loading && !result && <Button type="button" variant="secondary" onClick={() => { setError(''); setRefresh((value) => value + 1) }}>Try again</Button>}
      <form onSubmit={submit}>
        <fieldset className="team-member-picker" disabled={busy}>
          <legend>Available members</legend>
          {loading ? <LoadingScreen label="Finding available members…" /> : result?.items.length ? <div className="member-choice-list">
            {result.items.map((person) => <label className="member-choice" key={person._id}>
              <input type="checkbox" aria-label={`Select ${person.name}`} checked={selected.some((item) => item._id === person._id)} onChange={() => toggle(person)} />
              <span className="member-choice-name"><strong>{person.name}</strong><small>{person.email}</small></span>
              <Badge value={person.role} kind="role" />
            </label>)}
          </div> : result && <p className="field-hint">No available members. All active people already belong to a team. You can change their team in Team members.</p>}
          {result && <Pagination page={result.page} limit={result.limit} total={result.total} onPage={setPage} />}
        </fieldset>
        <p className="field-hint" aria-live="polite">{selected.length} selected</p>
        <div className="dialog-actions">
          <Button type="button" variant="secondary" onClick={close} disabled={busy}>Cancel</Button>
          <Button type="submit" busy={busy} disabled={loading || !result || !selected.length}><UserPlus size={18} /> Add selected</Button>
        </div>
      </form>
    </div>
  </dialog>
}
