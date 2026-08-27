import { useState } from 'react';
import { RotateCcw } from 'lucide-react';
import { Button } from './ui';
import { api } from '../lib/api';

interface Campaign {
  id: number;
  name: string;
  status: string;
  created_at: string;
  last_activity_at: string;
  sent: number;
  failed: number;
  total: number;
}

interface RecipientReview {
  target_id: number;
  company_name: string;
  email: string;
  contact_person?: string;
  country?: string;
  is_previously_contacted: boolean;
  previous_send_date?: string;
  previous_subject?: string;
  previous_company_name?: string;
  company_name_changed: boolean;
  contact_name_changed: boolean;
  country_changed: boolean;
  issues: string[];
}

interface ResendReview {
  campaign_id: number;
  campaign_name: string;
  total_recipients: number;
  previously_contacted: number;
  data_mismatches: number;
  requires_review: number;
  reviews: RecipientReview[];
}

type Step = 'select' | 'upload' | 'review' | 'approve' | 'sending';

export default function ResendCampaign() {
  const [showModal, setShowModal] = useState(false);
  const [step, setStep] = useState<Step>('select');
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selectedCampaign, setSelectedCampaign] = useState<Campaign | null>(null);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [review, setReview] = useState<ResendReview | null>(null);
  const [approved, setApproved] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<any>(null);

  const openResendWorkflow = async () => {
    setShowModal(true);
    setStep('select');
    setLoading(true);
    try {
      const data = await api.get<Campaign[]>('/api/campaigns/completed');
      setCampaigns(data);
    } catch (error) {
      alert(`Failed to load campaigns: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  const continueToUpload = () => {
    if (!selectedCampaign) return;
    setStep('upload');
    setUploadedFile(null);
  };

  const continueToReview = async () => {
    if (!selectedCampaign || !uploadedFile) return;
    setStep('review');
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', uploadedFile);
      const response = await fetch(
        `/api/campaigns/${selectedCampaign.id}/resend-review`,
        {
          method: 'POST',
          body: formData,
        }
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json() as ResendReview;
      setReview(data);
    } catch (error) {
      alert(`Failed to load review: ${error}`);
      setStep('upload');
    } finally {
      setLoading(false);
    }
  };

  const toggleApproval = (targetId: number) => {
    setApproved(prev => {
      const next = new Set(prev);
      if (next.has(targetId)) {
        next.delete(targetId);
      } else {
        next.add(targetId);
      }
      return next;
    });
  };

  const continueToSend = () => {
    if (approved.size === 0) {
      alert('Select at least one recipient to resend.');
      return;
    }
    setStep('approve');
  };

  const executeResend = async () => {
    if (!selectedCampaign) return;
    setSending(true);
    try {
      const data = await api.post(`/api/campaigns/${selectedCampaign.id}/execute-resend`, {
        approved_target_ids: Array.from(approved),
        resend_reason: 'User-approved resend',
      });
      setResult(data);
      setStep('sending');
    } catch (error) {
      alert(`Resend failed: ${error}`);
      setSending(false);
    }
  };

  const closeModal = () => {
    setShowModal(false);
    setStep('select');
    setSelectedCampaign(null);
    setUploadedFile(null);
    setReview(null);
    setApproved(new Set());
    setResult(null);
  };

  return (
    <>
      <Button
        onClick={openResendWorkflow}
        icon={<RotateCcw size={16} />}
      >
        Resend Campaign
      </Button>

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-latte dark:bg-[#1a1410] rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-latte dark:bg-[#1a1410] border-b border-caramel/15 p-4 flex justify-between items-center">
              <h2 className="text-xl font-bold text-latte dark:text-gold">
                {step === 'select' && 'Select Campaign to Resend'}
                {step === 'upload' && 'Upload Corrected Data'}
                {step === 'review' && 'Pre-Send Review'}
                {step === 'approve' && 'Confirm Resend'}
                {step === 'sending' && 'Resend Complete'}
              </h2>
              <button onClick={closeModal} className="text-2xl text-latte dark:text-gold hover:text-caramel">
                ×
              </button>
            </div>

            <div className="p-6">
              {/* STEP 1: Select Campaign */}
              {step === 'select' && (
                <div>
                  {loading ? (
                    <div className="text-center py-8">Loading campaigns...</div>
                  ) : campaigns.length === 0 ? (
                    <div className="text-center py-8 text-gray-500">
                      No completed campaigns available for resending.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {campaigns.map(campaign => (
                        <div
                          key={campaign.id}
                          onClick={() => setSelectedCampaign(campaign)}
                          className={`p-4 border-2 rounded cursor-pointer transition ${
                            selectedCampaign?.id === campaign.id
                              ? 'border-gold bg-gold/10 dark:bg-gold/5'
                              : 'border-caramel/25 dark:border-caramel/15 hover:border-gold/50'
                          }`}
                        >
                          <div className="font-semibold text-latte dark:text-gold">{campaign.name}</div>
                          <div className="text-sm text-latte/60 dark:text-latte/50">
                            Completed • {campaign.created_at}
                          </div>
                          <div className="text-sm mt-2 text-latte/70 dark:text-latte/60">
                            {campaign.sent} sent • {campaign.failed} failed • {campaign.total} total
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="mt-6 flex gap-3">
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={closeModal}
                      className="flex-1"
                    >
                      Cancel
                    </Button>
                    <Button
                      type="button"
                      onClick={continueToUpload}
                      disabled={!selectedCampaign || loading}
                      className="flex-1"
                    >
                      Continue to Upload
                    </Button>
                  </div>
                </div>
              )}

              {/* STEP 2: Upload Corrected Data */}
              {step === 'upload' && selectedCampaign && (
                <div>
                  <div className="bg-gold/10 dark:bg-gold/5 border border-gold/25 dark:border-gold/15 p-4 rounded mb-4">
                    <div className="font-semibold text-gold dark:text-gold">
                      Upload Corrected Data
                    </div>
                    <div className="text-sm text-latte/70 dark:text-latte/60 mt-2">
                      Upload a CSV or XLSX file with corrected company names and contact info to resend with updated data.
                    </div>
                  </div>

                  <div className="mb-6">
                    <label className="block text-sm font-medium mb-2">
                      Company File
                    </label>
                    <input
                      type="file"
                      accept=".csv,.xlsx,.xls,.ods,.tsv"
                      onChange={(e) => setUploadedFile(e.target.files?.[0] || null)}
                      className="block w-full text-sm border dark:border-gray-700 rounded p-2"
                    />
                    {uploadedFile && (
                      <div className="text-sm text-green-600 dark:text-green-400 mt-2">
                        ✓ {uploadedFile.name}
                      </div>
                    )}
                  </div>

                  <div className="flex gap-3">
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => setStep('select')}
                      className="flex-1"
                    >
                      Back
                    </Button>
                    <Button
                      type="button"
                      onClick={continueToReview}
                      disabled={!uploadedFile || loading}
                      className="flex-1"
                    >
                      Continue to Review
                    </Button>
                  </div>
                </div>
              )}

              {/* STEP 3: Pre-Send Review */}
              {step === 'review' && review && (
                <div>
                  <div className="bg-gold/10 dark:bg-gold/5 border border-gold/25 dark:border-gold/15 p-4 rounded mb-4">
                    <div className="font-semibold text-gold dark:text-gold">
                      ⚠️ Pre-Send Review
                    </div>
                    <div className="text-sm text-latte/70 dark:text-latte/60 mt-2">
                      {review.previously_contacted} previously contacted recipients detected.
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 mb-6">
                    <div className="p-3 bg-caramel/10 dark:bg-caramel/5 border border-caramel/15 rounded">
                      <div className="text-2xl font-bold text-latte dark:text-gold">{review.total_recipients}</div>
                      <div className="text-sm text-latte/60 dark:text-latte/50">Total Recipients</div>
                    </div>
                    <div className="p-3 bg-caramel/10 dark:bg-caramel/5 border border-caramel/15 rounded">
                      <div className="text-2xl font-bold text-latte dark:text-gold">{review.previously_contacted}</div>
                      <div className="text-sm text-latte/60 dark:text-latte/50">Previously Contacted</div>
                    </div>
                    <div className="p-3 bg-caramel/10 dark:bg-caramel/5 border border-caramel/15 rounded">
                      <div className="text-2xl font-bold text-latte dark:text-gold">{review.data_mismatches}</div>
                      <div className="text-sm text-latte/60 dark:text-latte/50">Data Changes</div>
                    </div>
                    <div className="p-3 bg-caramel/10 dark:bg-caramel/5 border border-caramel/15 rounded">
                      <div className="text-2xl font-bold text-latte dark:text-gold">{review.requires_review}</div>
                      <div className="text-sm text-latte/60 dark:text-latte/50">Requires Review</div>
                    </div>
                  </div>

                  <div className="space-y-3 max-h-96 overflow-y-auto mb-6">
                    {review.reviews
                      .filter(r => r.is_previously_contacted)
                      .map(recipient => (
                        <div
                          key={recipient.target_id}
                          className="p-3 border border-caramel/15 dark:border-caramel/10 rounded bg-latte/5 dark:bg-caramel/5"
                        >
                          <div className="flex items-start gap-3">
                            <input
                              type="checkbox"
                              checked={approved.has(recipient.target_id)}
                              onChange={() => toggleApproval(recipient.target_id)}
                              className="mt-1"
                            />
                            <div className="flex-1">
                              <div className="font-semibold text-latte dark:text-gold">{recipient.company_name}</div>
                              <div className="text-sm text-latte/60 dark:text-latte/50">
                                {recipient.email}
                              </div>
                              {recipient.previous_company_name &&
                                recipient.company_name_changed && (
                                  <div className="text-sm mt-2 p-2 bg-caramel/10 dark:bg-caramel/5 border border-caramel/25 rounded">
                                    <span className="text-latte/70 dark:text-gold/80">
                                      Previous: {recipient.previous_company_name}
                                    </span>
                                  </div>
                                )}
                              {recipient.previous_send_date && (
                                <div className="text-xs text-latte/50 dark:text-latte/40 mt-2">
                                  Last sent: {new Date(recipient.previous_send_date).toLocaleString()}
                                </div>
                              )}
                              {recipient.issues.length > 0 && (
                                <div className="text-xs text-gold/70 dark:text-gold/60 mt-2">
                                  Issues: {recipient.issues.join(', ')}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                  </div>

                  <div className="text-sm font-semibold text-gold dark:text-gold mb-6">
                    {approved.size} recipient(s) selected for resend
                  </div>

                  <div className="flex gap-3">
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => {
                        setStep('select');
                        setApproved(new Set());
                      }}
                      className="flex-1"
                    >
                      Back
                    </Button>
                    <Button
                      type="button"
                      onClick={continueToSend}
                      disabled={approved.size === 0}
                      className="flex-1"
                    >
                      Continue to Send
                    </Button>
                  </div>
                </div>
              )}

              {/* STEP 3: Confirm Resend */}
              {step === 'approve' && selectedCampaign && (
                <div>
                  <div className="bg-gold/10 dark:bg-gold/5 border border-gold/25 dark:border-gold/15 p-4 rounded mb-6">
                    <div className="font-semibold text-gold dark:text-gold">
                      Confirm Resend
                    </div>
                    <div className="text-sm text-latte/70 dark:text-latte/60 mt-2">
                      You are about to resend {approved.size} email(s) from{' '}
                      <strong>{selectedCampaign.name}</strong>.
                    </div>
                    <div className="text-sm text-latte/70 dark:text-latte/60 mt-2">
                      These recipients were previously contacted.
                    </div>
                  </div>

                  <div className="p-4 bg-caramel/10 dark:bg-caramel/5 border border-caramel/15 rounded mb-6">
                    <div className="text-center">
                      <div className="text-3xl font-bold text-latte dark:text-gold">{approved.size}</div>
                      <div className="text-latte/60 dark:text-latte/50">approved resend(s)</div>
                    </div>
                  </div>

                  <div className="flex gap-3">
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => setStep('review')}
                      className="flex-1"
                    >
                      Back
                    </Button>
                    <Button
                      type="button"
                      variant="danger"
                      onClick={executeResend}
                      disabled={sending}
                      className="flex-1"
                    >
                      {sending ? 'Sending...' : 'Confirm & Send'}
                    </Button>
                  </div>
                </div>
              )}

              {/* STEP 4: Complete */}
              {step === 'sending' && result && (
                <div>
                  <div className="bg-gold/10 dark:bg-gold/5 border border-gold/25 dark:border-gold/15 p-4 rounded mb-4">
                    <div className="font-semibold text-gold dark:text-gold">
                      ✅ Resend Complete
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 mb-6">
                    <div className="p-3 bg-caramel/10 dark:bg-caramel/5 border border-caramel/15 rounded">
                      <div className="text-2xl font-bold text-latte dark:text-gold">
                        {result.sent_count}
                      </div>
                      <div className="text-sm text-latte/60 dark:text-latte/50">Sent</div>
                    </div>
                    <div className="p-3 bg-gold/10 dark:bg-gold/5 border border-gold/15 rounded">
                      <div className="text-2xl font-bold text-latte dark:text-gold">
                        {result.failed_count}
                      </div>
                      <div className="text-sm text-latte/60 dark:text-latte/50">Failed</div>
                    </div>
                  </div>

                  <Button
                    type="button"
                    onClick={closeModal}
                    className="w-full"
                  >
                    Close
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
