import { ArrowRight, Briefcase, Send, Package } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../lib/api'
import { useAuth } from '../lib/auth'

/**
 * The choice between the two halves of the business.
 *
 * Inbound quoting and outbound prospecting are different jobs done at
 * different times, and putting both in one sidebar made twelve links where a
 * person only ever needs six. Pick a side here and the app shows only that
 * side's navigation.
 */
export function Hub() {
  const { user } = useAuth()
  const [counts, setCounts] = useState<{ quotes: number; outreach: number; due: number; products: number } | null>(
    null,
  )

  useEffect(() => {
    let cancelled = false
    Promise.all([
      api.listContacts().catch(() => []),
      api.outreachStats().catch(() => null),
      api.get('/api/bevi-stoq/products').catch(() => []),
    ]).then(([quotes, stats, products]) => {
      if (cancelled) return
      setCounts({
        quotes: quotes.length,
        outreach: stats?.total ?? 0,
        due: (stats?.due_today ?? 0) + (stats?.overdue ?? 0),
        products: products.length ?? 0,
      })
    })
    return () => {
      cancelled = true
    }
  }, [])

  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'
  const firstName = user?.name?.split(' ')[0] ?? ''

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-4xl flex-col justify-center">
      <div className="animate-fade-in-up-sm mb-10 text-center">
        <h1 className="font-display text-4xl text-latte">
          {greeting}
          {firstName ? `, ${firstName}` : ''}
        </h1>
        <p className="mt-2 text-sm text-latte/50">Where are you working today?</p>
      </div>

      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        <WorkspaceCard
          to="/app/trade"
          icon={<Briefcase size={24} />}
          title="Trade Desk"
          blurb="Quotes and RFQs, how far each deal has got, documents and shipment follow-ups."
          stat={counts ? `${counts.quotes} quote${counts.quotes === 1 ? '' : 's'}` : ' '}
          delay={0}
        />
        <WorkspaceCard
          to="/app/outreach"
          icon={<Send size={24} />}
          title="Outreach"
          blurb="Who we contacted, where we contacted them, what they replied, and when to chase."
          stat={
            counts
              ? counts.due > 0
                ? `${counts.due} due now · ${counts.outreach} tracked`
                : `${counts.outreach} tracked`
              : ' '
          }
          urgent={!!counts && counts.due > 0}
          delay={70}
        />
        <WorkspaceCard
          to="/app/bevi-stoq"
          icon={<Package size={24} />}
          title="Bevi Stoq"
          blurb="Inventory management, stock levels, product categories, and warehouse locations."
          stat={counts ? `${counts.products} product${counts.products === 1 ? '' : 's'}` : ' '}
          delay={140}
        />
      </div>
    </div>
  )
}

function WorkspaceCard({
  to,
  icon,
  title,
  blurb,
  stat,
  urgent = false,
  delay,
}: {
  to: string
  icon: React.ReactNode
  title: string
  blurb: string
  stat: string
  urgent?: boolean
  delay: number
}) {
  return (
    <Link
      to={to}
      style={{ animationDelay: `${delay}ms` }}
      className="animate-fade-in-up-sm group block rounded-2xl border border-caramel/20 bg-espresso/50 p-7 transition-all duration-200 hover:border-gold/45 hover:bg-espresso/70"
    >
      <div className="mb-5 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-gold/12 text-gold transition group-hover:bg-gold/20">
        {icon}
      </div>
      <h2 className="font-display text-2xl text-latte">{title}</h2>
      <p className="mt-2 text-sm leading-relaxed text-latte/55">{blurb}</p>
      <div className="mt-5 flex items-center justify-between border-t border-caramel/12 pt-4">
        <span className={urgent ? 'text-sm font-medium text-gold' : 'text-sm text-latte/45'}>
          {stat}
        </span>
        <ArrowRight
          size={17}
          className="text-latte/35 transition-transform group-hover:translate-x-1 group-hover:text-gold"
        />
      </div>
    </Link>
  )
}
