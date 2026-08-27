import { useState } from 'react';
import { RotateCcw } from 'lucide-react';
import { Button } from './ui';

interface ResendRecipient {
  email: string;
  company_name: string;
  contact_person?: string;
  is_in_history: boolean;
  last_sent_date?: string;
}

interface ResendReview {
  total_recipients: number;
  previously_contacted: number;
  recipients: ResendRecipient[];
}

type Step = 'upload' | 'mode-select' | 'sending';
type SendingMode = 'manual' | 'automatic';

export default function ResendCampaign() {
  const [showModal, setShowModal] = useState(false);
  const [step, setStep] = useState<Step>('upload');
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [campaignName, setCampaignName] = useState('');
  const [review, setReview] = useState<ResendReview | null>(null);
  const [sendingMode, setSendingMode] = useState<SendingMode>('manual');
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<any>(null);

  const openResendWorkflow = () => {
    setShowModal(true);
    setStep('upload');
    setUploadedFile(null);
    setCampaignName('');
    setReview(null);
    setSendingMode('manual');
    setResult(null);
  };

  const continueToModeSelect = async () => {
    if (!uploadedFile || !campaignName.trim()) return;
    setStep('mode-select');
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', uploadedFile);
      const response = await fetch('/api/resend/review', {
        method: 'POST',
        body: formData,
      });

      // Get response text first to debug issues
      const responseText = await response.text();
      console.error(`API Response [${response.status}]: ${responseText}`);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${responseText || 'No response body'}`);
      }

      if (!responseText) {
        throw new Error('Empty response from server');
      }

      try {
        const data = JSON.parse(responseText) as ResendReview;
        setReview(data);
      } catch (jsonError) {
        throw new Error(`Invalid JSON response: ${responseText.substring(0, 200)}`);
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      alert(`Failed to load review:\n\n${errorMsg}`);
      console.error('Review error:', error);
      setStep('upload');
    } finally {
      setLoading(false);
    }
  };

  const executeResend = async () => {
    if (!uploadedFile || !review || !campaignName.trim()) return;
    setSending(true);
    try {
      const formData = new FormData();
      formData.append('file', uploadedFile);
      formData.append('campaign_name', campaignName);
      formData.append('sending_mode', sendingMode);
      formData.append('resend_reason', 'User-approved corrected data resend');

      const response = await fetch('/api/resend/send', {
        method: 'POST',
        body: formData,
      });

      const responseText = await response.text();
      console.error(`Send API Response [${response.status}]: ${responseText}`);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${responseText || 'No response body'}`);
      }

      if (!responseText) {
        throw new Error('Empty response from server');
      }

      try {
        const data = JSON.parse(responseText);
        setResult(data);
        setStep('sending');
      } catch (jsonError) {
        throw new Error(`Invalid JSON response: ${responseText.substring(0, 200)}`);
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      alert(`Resend failed:\n\n${errorMsg}`);
      console.error('Send error:', error);
      setSending(false);
    }
  };

  const closeModal = () => {
    setShowModal(false);
    setStep('upload');
    setUploadedFile(null);
    setCampaignName('');
    setReview(null);
    setSendingMode('manual');
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
          <div className="bg-[#2A1A12] rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-[#2A1A12] border-b border-caramel/15 p-4 flex justify-between items-center">
              <h2 className="text-xl font-bold text-latte">
                {step === 'upload' && 'Resend Campaign'}
                {step === 'mode-select' && 'Choose Sending Preferences'}
                {step === 'sending' && 'Resend Complete'}
              </h2>
              <button onClick={closeModal} className="text-2xl text-latte hover:text-caramel">
                ×
              </button>
            </div>

            <div className="p-6">
              {/* STEP 1: Upload File */}
              {step === 'upload' && (
                <div>
                  <div className="space-y-6">
                    <div>
                      <h3 className="text-lg font-semibold text-latte mb-2">Resend</h3>
                      <p className="text-sm text-latte/70">Upload your cleaned company list — CSV or XLSX</p>
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-latte/60 uppercase tracking-wide mb-2">
                        Company file
                      </label>
                      <div className="relative">
                        <input
                          type="file"
                          accept=".csv,.xlsx,.xls,.ods,.tsv"
                          onChange={(e) => setUploadedFile(e.target.files?.[0] || null)}
                          className="hidden"
                          id="resend-file-input"
                        />
                        <label
                          htmlFor="resend-file-input"
                          className="flex items-center gap-3 p-3 bg-[#1a1410] border border-caramel/25 rounded cursor-pointer hover:border-caramel/50"
                        >
                          <span className="px-3 py-2 bg-gold/20 text-gold rounded text-sm font-medium">
                            Choose file
                          </span>
                          <span className="text-latte/70">
                            {uploadedFile ? uploadedFile.name : 'No file chosen'}
                          </span>
                        </label>
                      </div>
                      <p className="text-xs text-latte/50 mt-2">
                        Excel, CSV, TSV, .xls or .ods — column headings are matched automatically, and a file named wrongly is still read correctly
                      </p>
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-latte/60 uppercase tracking-wide mb-2">
                        Campaign name
                      </label>
                      <input
                        type="text"
                        value={campaignName}
                        onChange={(e) => setCampaignName(e.target.value)}
                        placeholder="e.g., Coffee Buyers - Updated Info"
                        className="w-full px-3 py-2 bg-[#1a1410] border border-caramel/25 rounded text-latte placeholder:text-latte/40 focus:outline-none focus:border-caramel/50"
                      />
                      <p className="text-xs text-latte/50 mt-2">
                        Give this resend campaign a descriptive name for your records.
                      </p>
                    </div>

                    <div>
                      <p className="text-sm text-gold bg-gold/10 border border-gold/25 p-3 rounded">
                        ℹ️ We'll identify which recipients were previously contacted and show them for resend.
                      </p>
                    </div>
                  </div>

                  <div className="mt-8 flex gap-3">
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
                      onClick={continueToModeSelect}
                      disabled={!uploadedFile || !campaignName.trim() || loading}
                      className="flex-1"
                    >
                      {loading ? 'Analyzing...' : 'Continue'}
                    </Button>
                  </div>
                </div>
              )}

              {/* STEP 2: Choose Sending Mode */}
              {step === 'mode-select' && review && (
                <div>
                  <div className="space-y-6">
                    {/* Summary */}
                    <div className="bg-gold/10 border border-gold/25 p-4 rounded">
                      <div className="font-semibold text-gold mb-2">
                        📊 Upload Summary
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <div className="text-2xl font-bold text-latte">{review.total_recipients}</div>
                          <div className="text-xs text-latte/60">Total Recipients</div>
                        </div>
                        <div>
                          <div className="text-2xl font-bold text-gold">{review.previously_contacted}</div>
                          <div className="text-xs text-latte/60">Previously Contacted</div>
                        </div>
                      </div>
                    </div>

                    {/* Sending Mode Selection */}
                    <div>
                      <label className="block text-xs font-medium text-latte/60 uppercase tracking-wide mb-3">
                        Sending Preference
                      </label>
                      <div className="space-y-3">
                        <label className="flex items-start gap-3 p-3 border border-caramel/25 rounded cursor-pointer hover:bg-[#1a1410]">
                          <input
                            type="radio"
                            name="sending-mode"
                            value="manual"
                            checked={sendingMode === 'manual'}
                            onChange={(e) => setSendingMode(e.target.value as SendingMode)}
                            className="w-4 h-4 mt-1"
                          />
                          <div className="flex-1">
                            <div className="text-sm font-medium text-latte">Let me read each email first</div>
                            <div className="text-xs text-latte/50 mt-1">Show each generated email before sending. You can approve, edit, skip, or reject each one.</div>
                          </div>
                        </label>
                        <label className="flex items-start gap-3 p-3 border border-caramel/25 rounded cursor-pointer hover:bg-[#1a1410]">
                          <input
                            type="radio"
                            name="sending-mode"
                            value="automatic"
                            checked={sendingMode === 'automatic'}
                            onChange={(e) => setSendingMode(e.target.value as SendingMode)}
                            className="w-4 h-4 mt-1"
                          />
                          <div className="flex-1">
                            <div className="text-sm font-medium text-latte">Just send them — 50 a day until done</div>
                            <div className="text-xs text-latte/50 mt-1">Emails are automatically approved and queued according to the daily sending limit.</div>
                          </div>
                        </label>
                      </div>
                      <p className="text-xs text-latte/50 mt-3">
                        Nothing goes out until you confirm the resend.
                      </p>
                    </div>

                    {/* Previously Contacted Preview */}
                    {review.previously_contacted > 0 && (
                      <div>
                        <div className="text-xs font-medium text-latte/60 uppercase tracking-wide mb-2">
                          Previously Contacted Recipients ({review.previously_contacted})
                        </div>
                        <div className="space-y-2 max-h-48 overflow-y-auto">
                          {review.recipients
                            .filter(r => r.is_in_history)
                            .slice(0, 5)
                            .map((recipient) => (
                              <div key={recipient.email} className="p-2 bg-[#1a1410] border border-caramel/15 rounded text-xs">
                                <div className="text-latte">{recipient.company_name}</div>
                                <div className="text-latte/50">{recipient.email}</div>
                              </div>
                            ))}
                          {review.previously_contacted > 5 && (
                            <div className="text-xs text-latte/50 p-2">
                              +{review.previously_contacted - 5} more recipients
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="mt-8 flex gap-3">
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => setStep('upload')}
                      className="flex-1"
                    >
                      Back
                    </Button>
                    <Button
                      type="button"
                      onClick={executeResend}
                      disabled={sending || review.previously_contacted === 0}
                      className="flex-1"
                    >
                      {sending ? 'Sending...' : 'Confirm & Queue'}
                    </Button>
                  </div>
                </div>
              )}

              {/* STEP 3: Complete */}
              {step === 'sending' && result && (
                <div>
                  <div className="bg-gold/10 border border-gold/25 p-4 rounded mb-4">
                    <div className="font-semibold text-gold">
                      ✅ Resend Queued Successfully
                    </div>
                    {result.campaign_name && (
                      <div className="text-sm text-latte/70 mt-2">
                        Campaign: <span className="text-latte font-medium">{result.campaign_name}</span>
                      </div>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-3 mb-6">
                    <div className="p-3 bg-caramel/10 border border-caramel/15 rounded">
                      <div className="text-2xl font-bold text-gold">{result.queued_count}</div>
                      <div className="text-sm text-latte/60">Queued for Resend</div>
                    </div>
                    <div className="p-3 bg-caramel/10 border border-caramel/15 rounded">
                      <div className="text-2xl font-bold text-gold">{result.sending_mode === 'manual' ? 'Manual' : 'Auto'}</div>
                      <div className="text-sm text-latte/60">Sending Mode</div>
                    </div>
                  </div>

                  <div className="text-sm text-latte/70 mb-6 p-3 bg-[#1a1410] rounded">
                    {result.sending_mode === 'manual'
                      ? 'Review and approve each email before sending.'
                      : 'Emails will be sent automatically at 50 per day.'}
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
