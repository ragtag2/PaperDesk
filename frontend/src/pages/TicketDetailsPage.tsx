import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router'
import { CalendarDays, Check, ClipboardList, Pencil, Trash2, UserRound } from 'lucide-react'
import { api } from '../api/client'
import { CoordinationPanel } from '../components/CoordinationPanel'
import type { Assignee, Ticket, TicketCategory, TicketPriority, TicketStatus } from '../api/types'
import { useAuth } from '../app/AuthContext'
import { Alert, BackLink, Badge, Button, ConfirmDialog, Field, LoadingScreen, SelectField, TextAreaField } from '../components/Ui'
import { canDeleteTicket, canEditTicket, canTriageTicket, categories, priorities, shortDate, statuses } from '../features/tickets'

export function TicketDetailsPage() {
  const { id = '' } = useParams()
  const { user } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [ticket, setTicket] = useState<Ticket | null>(null)
  const [assignees, setAssignees] = useState<Assignee[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [refreshingCoordination, setRefreshingCoordination] = useState(false)
  const [coordinationError, setCoordinationError] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState((location.state as { notice?: string } | null)?.notice ?? '')
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState<TicketCategory>('software')
  const [status, setStatus] = useState<TicketStatus>('open')
  const [priority, setPriority] = useState<TicketPriority>('medium')
  const [assigneeId, setAssigneeId] = useState('')
  const canTriage = user ? canTriageTicket(user.role) : false

  function sync(next: Ticket) {
    setTicket(next); setTitle(next.title); setDescription(next.description); setCategory(next.category)
    setStatus(next.status); setPriority(next.priority); setAssigneeId(next.assigneeId ?? '')
  }

  useEffect(() => {
    let active = true
    setLoading(true); setTicket(null); setEditing(false); setCoordinationError('')
    api.tickets.get(id).then((item) => { if (active) { sync(item); setError('') } })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : 'Could not load this ticket.') })
      .finally(() => { if (active) setLoading(false) })
    if (canTriage) api.tickets.assignees().then((items) => { if (active) setAssignees(items) }).catch(() => {})
    return () => { active = false }
  }, [id, canTriage])

  const analysisTicketId = ticket?._id
  const ticketVersion = ticket?.updatedAt
  const analyzedAt = ticket?.coordination?.analyzedAt

  useEffect(() => {
    if (analysisTicketId !== id || !ticketVersion || (analyzedAt && Date.parse(analyzedAt) >= Date.parse(ticketVersion))) return
    let active = true
    let checks = 0
    let timer: ReturnType<typeof setTimeout>
    async function check() {
      checks += 1
      let complete = false
      try {
        const next = await api.tickets.get(id)
        if (!active) return
        // Refresh the analysis without changing unsaved details or triage fields.
        setTicket((current) => current?._id === id && current.updatedAt === next.updatedAt ? { ...current, coordination: next.coordination } : current)
        complete = !!next.coordination && Date.parse(next.coordination.analyzedAt) >= Date.parse(ticketVersion!)
      } catch { /* The refresh button remains available after background checks stop. */ }
      if (active && !complete && checks < 12) timer = setTimeout(check, 5000)
    }
    timer = setTimeout(check, 5000)
    return () => { active = false; clearTimeout(timer) }
  }, [id, analysisTicketId, ticketVersion, analyzedAt])

  async function refreshCoordination() {
    setRefreshingCoordination(true); setCoordinationError('')
    try {
      const next = await api.tickets.get(id)
      setTicket((current) => current?._id === id && current.updatedAt === next.updatedAt ? { ...current, coordination: next.coordination } : current)
    } catch (reason) { setCoordinationError(reason instanceof Error ? reason.message : 'Could not refresh coordination.') }
    finally { setRefreshingCoordination(false) }
  }

  async function saveDetails(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('')
    try { sync(await api.tickets.update(id, { title: title.trim(), description: description.trim(), category })); setEditing(false); setNotice('Ticket details saved.') }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not save this ticket.') }
    finally { setBusy(false) }
  }
  async function saveTriage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('')
    try { sync(await api.tickets.update(id, { status, priority, assigneeId: assigneeId || null })); setNotice('Ticket updates saved.') }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not update this ticket.') }
    finally { setBusy(false) }
  }
  async function remove() {
    setBusy(true); setError('')
    try { await api.tickets.remove(id); navigate('/tickets', { replace: true }) }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not delete this ticket.'); setConfirmDelete(false) }
    finally { setBusy(false) }
  }

  if (loading) return <LoadingScreen label="Opening the ticket…" />
  if (!ticket) return <div className="narrow-page"><BackLink to="/tickets">Back to tickets</BackLink>{error && <Alert>{error}</Alert>}</div>
  const canEdit = !!user && canEditTicket(ticket, user._id, user.role)
  const canDelete = !!user && canDeleteTicket(ticket, user._id, user.role)

  return <div className="details-page"><BackLink to="/tickets">Back to tickets</BackLink><div className="detail-heading"><div><div className="eyebrow">TICKET #{ticket._id.replace(/^t-/, '')} <span aria-hidden="true">✳</span></div><h1>{ticket.title}<span className="heading-period">.</span></h1><div className="detail-badges"><Badge value={ticket.status} /><Badge value={ticket.priority} kind="priority" /><Badge value={ticket.category} kind="category" /></div></div>{canDelete && <Button type="button" variant="quiet" className="delete-action" onClick={() => setConfirmDelete(true)}><Trash2 size={18} /> Delete</Button>}</div>{error && <Alert>{error}</Alert>}{notice && <Alert kind="success">{notice}</Alert>}<div className="detail-grid"><div className="detail-primary"><section className="paper-panel detail-description"><div className="detail-section-top"><div><span className="section-kicker">THE DETAILS</span><h2>What's happening?</h2></div>{canEdit && !editing && <Button type="button" variant="quiet" onClick={() => setEditing(true)}><Pencil size={16} /> Edit</Button>}</div>{editing ? <form onSubmit={saveDetails} className="edit-form"><Field id="edit-title" label="Title" value={title} onChange={(event) => setTitle(event.target.value)} maxLength={120} required /><TextAreaField id="edit-description" label="Description" rows={7} value={description} onChange={(event) => setDescription(event.target.value)} required /><SelectField id="edit-category" label="Category" value={category} onChange={(event) => setCategory(event.target.value as TicketCategory)}>{categories.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</SelectField><div className="inline-actions"><Button type="button" variant="secondary" onClick={() => { sync(ticket); setEditing(false) }}>Cancel</Button><Button type="submit" busy={busy}><Check size={18} /> Save changes</Button></div></form> : <p className="ticket-description-text">{ticket.description}</p>}</section><CoordinationPanel coordination={ticket.coordination} updatedAt={ticket.updatedAt} refreshing={refreshingCoordination} error={coordinationError} onRefresh={refreshCoordination} /><section className="detail-timeline paper-panel"><div className="detail-section-top"><div><span className="section-kicker">AT A GLANCE</span><h2>The paper trail</h2></div><ClipboardList size={24} /></div><div className="timeline-row"><span className="timeline-dot" /><div><strong>Ticket created</strong><span>Sent by {ticket.creator?.name ?? (ticket.creatorId === user?._id ? 'you' : 'a team member')}</span></div><time>{shortDate(ticket.createdAt)}</time></div>{ticket.updatedAt !== ticket.createdAt && <div className="timeline-row"><span className="timeline-dot timeline-dot-blue" /><div><strong>Last updated</strong><span>Most recent change</span></div><time>{shortDate(ticket.updatedAt)}</time></div>}</section></div><aside className="detail-sidebar"><section className="paper-panel detail-info"><span className="section-kicker">QUICK FACTS</span><h2>Ticket info</h2><div className="info-row"><span><CalendarDays size={17} /> Created</span><strong>{shortDate(ticket.createdAt)}</strong></div><div className="info-row"><span><UserRound size={17} /> Assigned to</span><strong>{ticket.assignee?.name ?? assignees.find((item) => item._id === ticket.assigneeId)?.name ?? (ticket.assigneeId ? 'Team member' : 'Unassigned')}</strong></div><div className="info-row"><span>✳ Category</span><strong>{categories.find((item) => item.value === ticket.category)?.label}</strong></div></section>{canTriage && <section className="paper-panel triage-panel"><span className="section-kicker">SUPPORT DESK</span><h2>Move it along</h2><p>Keep the team in the loop as this ticket progresses.</p><form onSubmit={saveTriage}><SelectField id="ticket-status" label="Status" value={status} onChange={(event) => setStatus(event.target.value as TicketStatus)}>{statuses.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</SelectField><SelectField id="ticket-priority" label="Priority" value={priority} onChange={(event) => setPriority(event.target.value as TicketPriority)}>{priorities.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</SelectField><SelectField id="ticket-assignee" label="Assign to" value={assigneeId} onChange={(event) => setAssigneeId(event.target.value)}><option value="">Unassigned</option>{assignees.map((item) => <option key={item._id} value={item._id}>{item.name}</option>)}</SelectField><Button type="submit" busy={busy} className="full-width">Save updates</Button></form></section>}</aside></div>{confirmDelete && <ConfirmDialog title="Delete this ticket?" description="This removes the ticket from the workspace. This action cannot be undone." confirmLabel="Delete ticket" danger busy={busy} onConfirm={remove} onClose={() => setConfirmDelete(false)} />}</div>
}
