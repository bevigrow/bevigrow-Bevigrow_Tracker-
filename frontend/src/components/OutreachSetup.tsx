/**
 * The three things that must be true before an email can be sent, and which
 * of them are done.
 *
 * There were three pages — mailbox, template, campaign — and nothing said they
 * were a sequence or which one you were missing. The page simply refused to
 * let you start and left you to work out why. A person setting this up for the
 * first time should be able to see the whole path and where they are on it.
 *
 * It disappears once all three are done, because a permanent checklist of
 * finished work is clutter.
 */
import { ArrowRight, Check } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Card } from './ui'

export interface SetupState {
  mailboxReady: boolean
  mailboxVerified: boolean
  hasTemplate: boolean
  hasCampaign: boolean
}

interface Step {
  title: string
  detail: string
  done: boolean
  to?: string
  action?: string
  onAction?: () => void
}

export function OutreachSetup({
  state,
  onNewCampaign,
}: {
  state: SetupState
  onNewCampaign: () => void
}) {
  const steps: Step[] = [
    {
      title: 'Connect a sending mailbox',
      detail: state.mailboxReady
        ? state.mailboxVerified
          ? 'Connected and tested.'
          : 'Connected — press Test connection to be sure it works.'
        : 'Where your emails are sent from.',
      done: state.mailboxReady && state.mailboxVerified,
      to: '/app/outreach/settings',
      action: state.mailboxReady ? 'Test it' : 'Connect',
    },
    {
      title: 'Write your email',
      detail: state.hasTemplate
        ? 'Saved. Only the company name and a company-specific line change per email.'
        : 'One email, written once. The agent fills in the company details.',
      done: state.hasTemplate,
      to: '/app/outreach/settings',
      action: state.hasTemplate ? 'Edit' : 'Write it',
    },
    {
      title: 'Upload your company list',
      detail: state.hasCampaign
        ? 'Uploaded. Press Start and the agent works through it.'
        : 'Excel or CSV. Any column headings — they are matched for you.',
      done: state.hasCampaign,
      action: 'Upload',
      onAction: onNewCampaign,
    },
  ]

  if (steps.every((s) => s.done)) return null
  const current = steps.findIndex((s) => !s.done)

  return (
    <Card>
      <h2 className="font-display text-lg text-latte">Three steps to your first email</h2>
      <p className="mb-4 mt-0.5 text-[12px] text-latte/45">
        Once these are done, the agent sends on its own — fifty a day, and it keeps going when
        you close this page.
      </p>

      <ol className="space-y-2.5">
        {steps.map((step, i) => {
          const active = i === current
          return (
            <li
              key={step.title}
              className={`flex flex-wrap items-center gap-3 rounded-xl border px-4 py-3 transition ${
                step.done
                  ? 'border-emerald-400/25 bg-emerald-400/[0.06]'
                  : active
                    ? 'border-gold/40 bg-gold/[0.07]'
                    : 'border-caramel/12 bg-bean/20 opacity-60'
              }`}
            >
              <span
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[12px] font-semibold ${
                  step.done
                    ? 'bg-emerald-400/20 text-emerald-300'
                    : active
                      ? 'bg-gold/20 text-gold'
                      : 'bg-latte/10 text-latte/40'
                }`}
              >
                {step.done ? <Check size={14} /> : i + 1}
              </span>

              <div className="min-w-0 flex-1">
                <p className={`text-sm ${step.done ? 'text-latte/70' : 'text-latte'}`}>
                  {step.title}
                </p>
                <p className="text-[11.5px] text-latte/45">{step.detail}</p>
              </div>

              {!step.done &&
                (step.onAction ? (
                  <button
                    onClick={step.onAction}
                    className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-gold/15 px-3 py-1.5 text-[12px] font-semibold text-gold transition hover:bg-gold/25"
                  >
                    {step.action} <ArrowRight size={13} />
                  </button>
                ) : (
                  <Link
                    to={step.to ?? '#'}
                    className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-gold/15 px-3 py-1.5 text-[12px] font-semibold text-gold transition hover:bg-gold/25"
                  >
                    {step.action} <ArrowRight size={13} />
                  </Link>
                ))}
            </li>
          )
        })}
      </ol>
    </Card>
  )
}
