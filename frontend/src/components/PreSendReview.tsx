/**
 * Pre-send review screen showing all recipients before sending.
 * Detects previously contacted recipients, data changes, and flags requiring approval.
 */
import { AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'

import { Button, Card } from './ui'

export interface ReviewItem {
  target_id: number
  company_name: string
  email: string
  contact_person: string | null
  country: string | null
  is_new: boolean
  is_previously_contacted: boolean
  is_potential_duplicate: boolean
  has_data_changes: boolean
  previous_send_date: string | null
  previous_subject: string | null
  previous_company_name: string | null
  company_name_changed: boolean
  contact_name_changed: boolean
  country_changed: boolean
  issues: string[]
  user_approved: boolean
  approval_reason: string | null
}

export interface PreSendReviewData {
  total_recipients: number
  new_contacts: number
  previously_contacted: number
  potential_duplicates: number
  data_mismatches: number
  requires_review: number
  reviews: ReviewItem[]
}

interface Props {
  review: PreSendReviewData
  onApproveResend: (targetId: number, reason: string, notes?: string) => Promise<void>
  onSend: () => void
  loading: boolean
}

export function PreSendReview({ review, onApproveResend, onSend, loading }: Props) {
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())
  const [approvingId, setApprovingId] = useState<number | null>(null)

  const toggleExpanded = (id: number) => {
    const newExpanded = new Set(expandedIds)
    if (newExpanded.has(id)) {
      newExpanded.delete(id)
    } else {
      newExpanded.add(id)
    }
    setExpandedIds(newExpanded)
  }

  const flaggedReviews = review.reviews.filter(
    (r) => r.is_previously_contacted || r.has_data_changes || r.is_potential_duplicate
  )

  const approvedResends = flaggedReviews.filter((r) => r.user_approved)

  return (
    <div className="space-y-6">
      {/* Summary Stats */}
      <Card>
        <h2 className="mb-4 font-display text-lg text-latte">Pre-Send Review</h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label="Total" value={review.total_recipients} />
          <Stat label="New" value={review.new_contacts} tone="text-emerald-300" />
          <Stat label="Previously Contacted" value={review.previously_contacted} tone="text-gold" />
          <Stat label="Potential Duplicates" value={review.potential_duplicates} tone="text-red-300" />
          <Stat label="Data Changes" value={review.data_mismatches} tone="text-amber-300" />
          <Stat label="Requires Review" value={review.requires_review} tone="text-gold" />
        </div>
      </Card>

      {/* Flagged Records */}
      {flaggedReviews.length > 0 && (
        <Card>
          <div className="mb-4 flex items-start gap-3 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3">
            <AlertTriangle size={18} className="mt-0.5 shrink-0 text-amber-400" />
            <div className="text-sm text-latte/75">
              <p className="font-medium">⚠️ {flaggedReviews.length} previously contacted companies detected.</p>
              <p className="mt-1 text-xs text-latte/50">
                The system has NOT automatically resent these emails. Review each record below. Some may be
                legitimate corrections or intentional resends.
              </p>
            </div>
          </div>

          <div className="space-y-3">
            {flaggedReviews.map((review) => (
              <div key={review.target_id} className="rounded-lg border border-caramel/15 bg-bean/30 p-4">
                <button
                  onClick={() => toggleExpanded(review.target_id)}
                  className="w-full text-left"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <p className="font-medium text-latte">{review.company_name}</p>
                        {review.is_potential_duplicate && (
                          <span className="rounded-full bg-red-500/20 px-2 py-0.5 text-[10px] font-semibold text-red-300">
                            Duplicate
                          </span>
                        )}
                        {review.has_data_changes && (
                          <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] font-semibold text-amber-300">
                            Data Changed
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-latte/45">{review.email}</p>
                      {review.previous_send_date && (
                        <p className="mt-1 text-[10px] text-latte/40">
                          Previously sent: {new Date(review.previous_send_date).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-3">
                      {review.user_approved && (
                        <span className="text-[11px] font-semibold text-emerald-300">✓ Approved</span>
                      )}
                      {expandedIds.has(review.target_id) ? (
                        <ChevronUp size={16} className="text-latte/50" />
                      ) : (
                        <ChevronDown size={16} className="text-latte/50" />
                      )}
                    </div>
                  </div>
                </button>

                {expandedIds.has(review.target_id) && (
                  <div className="mt-4 space-y-4 border-t border-caramel/10 pt-4">
                    {/* Data Comparison */}
                    {review.has_data_changes && (
                      <div className="bg-espresso/30 rounded p-3">
                        <h4 className="mb-2 text-xs font-semibold text-latte/70">Detected Changes</h4>
                        <ul className="space-y-1 text-[11px] text-latte/60">
                          {review.company_name_changed && (
                            <li>
                              • Company: <span className="line-through">{review.previous_company_name}</span> →
                              <span className="ml-1 font-medium text-latte">{review.company_name}</span>
                            </li>
                          )}
                          {review.contact_name_changed && (
                            <li>• Contact person changed</li>
                          )}
                          {review.country_changed && (
                            <li>• Country changed</li>
                          )}
                        </ul>
                      </div>
                    )}

                    {/* Previous Send Info */}
                    {review.previous_subject && (
                      <div>
                        <h4 className="mb-1 text-xs font-semibold text-latte/70">Previous Email</h4>
                        <p className="rounded bg-espresso/30 p-2 text-[11px] text-latte/60">
                          {review.previous_subject}
                        </p>
                      </div>
                    )}

                    {/* Issues */}
                    {review.issues.length > 0 && (
                      <div>
                        <h4 className="mb-1 text-xs font-semibold text-latte/70">Issues</h4>
                        <ul className="space-y-1">
                          {review.issues.map((issue, idx) => (
                            <li key={idx} className="text-[11px] text-amber-300">
                              • {issue}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Approval Section */}
                    {!review.user_approved && (
                      <div className="rounded border border-caramel/20 bg-espresso/50 p-3">
                        <div className="mb-2">
                          <label className="flex items-center gap-2 text-sm text-latte">
                            <input
                              type="checkbox"
                              disabled={approvingId === review.target_id}
                              onChange={() => {
                                if (confirm('Approve resend to this company?')) {
                                  setApprovingId(review.target_id)
                                  onApproveResend(review.target_id, 'data_correction').then(() => {
                                    setApprovingId(null)
                                  })
                                }
                              }}
                              className="h-4 w-4 cursor-pointer accent-gold"
                            />
                            Approve corrected resend
                          </label>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Send Summary */}
      <Card className="border-emerald-500/20 bg-emerald-500/5">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-latte">
              Ready to send{' '}
              <span className="font-semibold text-emerald-300">{review.new_contacts} new emails</span>
              {approvedResends.length > 0 && (
                <>
                  {' '}
                  + <span className="font-semibold text-amber-300">{approvedResends.length} approved resends</span>
                </>
              )}
            </p>
            <p className="mt-1 text-[11px] text-latte/45">
              {review.total_recipients - review.new_contacts - approvedResends.length} records will be skipped
            </p>
          </div>
          <Button onClick={onSend} loading={loading} className="px-6">
            Send All
          </Button>
        </div>
      </Card>
    </div>
  )
}

function Stat({ label, value, tone = 'text-latte' }: { label: string; value: number; tone?: string }) {
  return (
    <div>
      <p className={`font-body text-2xl font-semibold ${tone}`}>{value}</p>
      <p className="text-[10.5px] uppercase tracking-wider text-latte/45">{label}</p>
    </div>
  )
}
