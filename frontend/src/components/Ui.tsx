import { useEffect, useRef } from 'react'
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { AlertCircle, ArrowLeft, ArrowRight, Inbox, LoaderCircle, X } from 'lucide-react'
import { Link } from 'react-router'
import { labelFor } from '../features/tickets'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'quiet' | 'danger'; busy?: boolean; children: ReactNode }
export function Button({ variant = 'primary', busy, children, className = '', disabled, ...props }: ButtonProps) {
  return <button className={`button button-${variant} ${className}`} disabled={disabled || busy} {...props}>{busy && <LoaderCircle className="spin" size={18} aria-hidden="true" />}{children}</button>
}

export function Field({ label, id, hint, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string; id: string; hint?: string }) {
  return <div className="field"><label htmlFor={id}>{label}</label><input id={id} {...props} />{hint && <small className="field-hint">{hint}</small>}</div>
}
export function TextAreaField({ label, id, hint, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string; id: string; hint?: string }) {
  return <div className="field"><label htmlFor={id}>{label}</label><textarea id={id} {...props} />{hint && <small className="field-hint">{hint}</small>}</div>
}
export function SelectField({ label, id, children, ...props }: SelectHTMLAttributes<HTMLSelectElement> & { label: string; id: string; children: ReactNode }) {
  return <div className="field"><label htmlFor={id}>{label}</label><select id={id} {...props}>{children}</select></div>
}

export function Alert({ children, kind = 'error' }: { children: ReactNode; kind?: 'error' | 'success' | 'info' }) {
  return <div className={`alert alert-${kind}`} role={kind === 'error' ? 'alert' : 'status'}>{kind === 'error' && <AlertCircle size={19} aria-hidden="true" />}{children}</div>
}

export function Badge({ value, kind = 'status' }: { value: string; kind?: 'status' | 'priority' | 'category' | 'role' }) {
  return <span className={`badge badge-${kind} badge-${value}`}>{labelFor(value)}</span>
}

export function PageHeading({ eyebrow, title, description, action }: { eyebrow: string; title: string; description?: string; action?: ReactNode }) {
  return <div className="page-heading"><div><div className="eyebrow"><span aria-hidden="true">✳</span> {eyebrow}</div><h1>{title}<span className="heading-period">.</span></h1>{description && <p>{description}</p>}</div>{action && <div className="page-heading-action">{action}</div>}</div>
}

export function LoadingScreen({ label = 'Getting things ready…' }: { label?: string }) {
  return <div className="loading-screen" role="status"><LoaderCircle className="spin" size={28} /><span>{label}</span></div>
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <div className="empty-state"><div className="empty-icon"><Inbox size={28} strokeWidth={2.2} /></div><h2>{title}</h2><p>{description}</p>{action}</div>
}

export function Pagination({ page, limit, total, onPage }: { page: number; limit: number; total: number; onPage: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / limit))
  if (pages <= 1) return null
  return <div className="pagination"><span>Showing {(page - 1) * limit + 1}–{Math.min(page * limit, total)} of {total}</span><div><Button variant="quiet" type="button" onClick={() => onPage(page - 1)} disabled={page <= 1}><ArrowLeft size={17} /> Previous</Button><span className="page-count">{page} / {pages}</span><Button variant="quiet" type="button" onClick={() => onPage(page + 1)} disabled={page >= pages}>Next <ArrowRight size={17} /></Button></div></div>
}

export function ConfirmDialog({ title, description, confirmLabel, danger = false, busy = false, onConfirm, onClose }: { title: string; description: string; confirmLabel: string; danger?: boolean; busy?: boolean; onConfirm: () => void; onClose: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  useEffect(() => { const dialog = dialogRef.current; dialog?.showModal(); return () => dialog?.close() }, [])
  return <dialog ref={dialogRef} className="dialog" aria-labelledby="confirm-dialog-title" onCancel={onClose} onClick={(event) => { if (event.target === dialogRef.current) onClose() }}><div className="dialog-content"><button className="dialog-close icon-button" type="button" onClick={onClose} aria-label="Close dialog"><X size={20} /></button><span className="dialog-doodle" aria-hidden="true">!</span><h2 id="confirm-dialog-title">{title}</h2><p>{description}</p><div className="dialog-actions"><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button type="button" variant={danger ? 'danger' : 'primary'} busy={busy} onClick={onConfirm}>{confirmLabel}</Button></div></div></dialog>
}

export function BackLink({ to, children }: { to: string; children: ReactNode }) { return <Link className="back-link" to={to}><ArrowLeft size={17} /> {children}</Link> }
