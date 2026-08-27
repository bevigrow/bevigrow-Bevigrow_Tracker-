import { useState } from 'react';
import { RotateCcw } from 'lucide-react';
import { Button } from './ui';
import { api, tokenStore, API_BASE } from '../lib/api';

interface EmailTemplate {
  id: number;
  name: string;
  subject: string;
  placeholders: string[];
}

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

interface EmailPreview {
  subject: string;
  body: string;
  unfilled_placeholders: string[];
  can_send: boolean;
}

type Step = 'upload' | 'review' | 'template' | 'preview' | 'mode-select' | 'sending';
type SendingMode = 'manual' | 'automatic';

export default function ResendCampaign() {
  const [showModal, setShowModal] = useState(false);
  const [step, setStep] = useState<Step>('upload');
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [campaignName, setCampaignName] = useState('');
  const [review, setReview] = useState<ResendReview | null>(null);

  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
  const [preview, setPreview] = useState<EmailPreview | null>(null);

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
    setTemplates([]);
    setSelectedTemplateId(null);
    setPreview(null);
    setSendingMode('manual');
    setResult(null);
  };

  // Step 1: Upload & Review
  const continueToReview = async () => {
    if (!uploadedFile || !campaignName.trim()) return;
    setStep('review');
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', uploadedFile);

      const headers = new Headers();
      const token = tokenStore.get();
      if (token) headers.set('Authorization', `Bearer ${token}`);

      const response = await fetch(`${API_BASE}/api/resend/review`, {
        method: 'POST',
        body: formData,
        headers,
      });

      const responseText = await response.text();
      console.log(`Review Response [${response.status}]:`, responseText);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${responseText || 'No response body'}`);
      }

      if (!responseText) {
        throw new Error('Empty response from server');
      }

      const data = JSON.parse(responseText) as ResendReview;
      if (data.total_recipients === 0) {
        throw new Error('No valid email addresses found in this file');
      }
      setReview(data);
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      alert(`Failed to analyze file:\n\n${errorMsg}`);
      console.error('Review error:', error);
      setStep('upload');
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Template Selection
  const continueToTemplate = async () => {
    if (!review) return;
    setStep('template');
    setLoading(true);
    try {
      const data = await api.get<any[]>('/api/resend/templates');
      setTemplates(data);
      if (data.length > 0) {
        setSelectedTemplateId(data[0].id);
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      alert(`Failed to load templates:\n\n${errorMsg}`);
      setStep('review');
    } finally {
      setLoading(false);
    }
  };

  // Step 3: Email Preview
  const continueToPreview = async () => {
    if (!selectedTemplateId || !review || review.total_recipients === 0) return;
    setStep('preview');
    setLoading(true);
    try {
      const sampleRecipient = review.recipients.find(r => r.is_in_history);
      if (!sampleRecipient) {
        throw new Error('No sample recipient found');
      }

      const formData = new FormData();
      formData.append('email', sampleRecipient.email);
      formData.append('company_name', sampleRecipient.company_name);
      formData.append('contact_person', sampleRecipient.contact_person || '');
      formData.append('country', '');
      formData.append('category', '');
      formData.append('template_id', selectedTemplateId.toString());

      const headers = new Headers();
      const token = tokenStore.get();
      if (token) headers.set('Authorization', `Bearer ${token}`);

      const response = await fetch(`${API_BASE}/api/resend/preview`, {
        method: 'POST',
        body: formData,
        headers,
      });

      if (!response.ok) throw new Error('Failed to generate preview');
      const data = await response.json() as EmailPreview;
      setPreview(data);
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      alert(`Failed to preview email:\n\n${errorMsg}`);
      setStep('template');
    } finally {
      setLoading(false);
    }
  };

  // Step 4: Mode Selection & Send
  const executeResend = async () => {
    if (!uploadedFile || !campaignName.trim() || !selectedTemplateId) return;
    setSending(true);
    try {
      const formData = new FormData();
      formData.append('file', uploadedFile);
      formData.append('campaign_name', campaignName);
      formData.append('template_id', selectedTemplateId.toString());
      formData.append('sending_mode', sendingMode);
      formData.append('resend_reason', 'User-approved corrected data resend');

      const headers = new Headers();
      const token = tokenStore.get();
      if (token) headers.set('Authorization', `Bearer ${token}`);

      const response = await fetch(`${API_BASE}/api/resend/send`, {
        method: 'POST',
        body: formData,
        headers,
      });

      const responseText = await response.text();
      console.log(`Send Response [${response.status}]:`, responseText);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${responseText || 'No response body'}`);
      }

      if (!responseText) {
        throw new Error('Empty response from server');
      }

      const data = JSON.parse(responseText);
      setResult(data);
      setStep('sending');
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
    setTemplates([]);
    setSelectedTemplateId(null);
    setPreview(null);
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
                {step === 'upload' && 'Resend Campaign - Upload'}
                {step === 'review' && 'Resend Campaign - Review'}
                {step === 'template' && 'Resend Campaign - Select Template'}
                {step === 'preview' && 'Resend Campaign - Preview Email'}
                {step === 'mode-select' && 'Resend Campaign - Choose Sending Mode'}
                {step === 'sending' && 'Resend Campaign - Complete'}
              </h2>
              <button onClick={closeModal} className="text-2xl text-latte hover:text-caramel">
                ×
              </button>
            </div>

            <div className="p-6">
              {/* STEP 1: Upload */}
              {step === 'upload' && (
                <div className="space-y-6">
                  <div>
                    <h3 className="text-lg font-semibold text-latte mb-2">Upload Corrected Data</h3>
                    <p className="text-sm text-latte/70">Upload your cleaned company list with corrected information</p>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-latte/60 uppercase tracking-wide mb-2">
                      Campaign Name
                    </label>
                    <input
                      type="text"
                      value={campaignName}
                      onChange={(e) => setCampaignName(e.target.value)}
                      placeholder="e.g., Coffee Buyers - Updated Contact Info"
                      className="w-full px-3 py-2 bg-[#1a1410] border border-caramel/25 rounded text-latte placeholder:text-latte/40 focus:outline-none focus:border-caramel/50"
                    />
                    <p className="text-xs text-latte/50 mt-2">
                      Give this resend campaign a descriptive name for your records.
                    </p>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-latte/60 uppercase tracking-wide mb-2">
                      Company File
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
                      Excel, CSV, TSV, .xls or .ods — column headings are matched automatically
                    </p>
                  </div>

                  <div className="mt-8 flex gap-3">
                    <Button type="button" variant="ghost" onClick={closeModal} className="flex-1">
                      Cancel
                    </Button>
                    <Button
                      type="button"
                      onClick={continueToReview}
                      disabled={!uploadedFile || !campaignName.trim() || loading}
                      className="flex-1"
                    >
                      {loading ? 'Analyzing...' : 'Continue'}
                    </Button>
                  </div>
                </div>
              )}

              {/* STEP 2: Review Previously Contacted */}
              {step === 'review' && review && (
                <div className="space-y-6">
                  <div className="bg-gold/10 border border-gold/25 p-4 rounded">
                    <div className="font-semibold text-gold mb-2">Analysis Results</div>
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

                  {review.previously_contacted > 0 && (
                    <div>
                      <div className="text-xs font-medium text-latte/60 uppercase tracking-wide mb-2">
                        Sample Recipients ({Math.min(5, review.previously_contacted)} of {review.previously_contacted})
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
                      </div>
                    </div>
                  )}

                  <div className="mt-8 flex gap-3">
                    <Button type="button" variant="ghost" onClick={() => setStep('upload')} className="flex-1">
                      Back
                    </Button>
                    <Button
                      type="button"
                      onClick={continueToTemplate}
                      disabled={loading}
                      className="flex-1"
                    >
                      {loading ? 'Loading...' : 'Continue to Template'}
                    </Button>
                  </div>
                </div>
              )}

              {/* STEP 3: Template Selection */}
              {step === 'template' && (
                <div className="space-y-6">
                  <div>
                    <h3 className="text-lg font-semibold text-latte mb-2">Select Email Template</h3>
                    <p className="text-sm text-latte/70">Choose a template to use for this resend campaign</p>
                  </div>

                  {templates.length === 0 ? (
                    <div className="p-4 bg-[#1a1410] border border-caramel/25 rounded text-latte/70">
                      No templates available. Please create one first in the Templates section.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {templates.map((template) => (
                        <label key={template.id} className="flex items-start gap-3 p-3 border border-caramel/25 rounded cursor-pointer hover:bg-[#1a1410]">
                          <input
                            type="radio"
                            name="template"
                            value={template.id}
                            checked={selectedTemplateId === template.id}
                            onChange={() => setSelectedTemplateId(template.id)}
                            className="w-4 h-4 mt-1"
                          />
                          <div className="flex-1">
                            <div className="font-medium text-latte">{template.name}</div>
                            <div className="text-xs text-latte/50 mt-1">Subject: {template.subject}</div>
                            {template.placeholders.length > 0 && (
                              <div className="text-xs text-gold mt-1">
                                Placeholders: {template.placeholders.join(', ')}
                              </div>
                            )}
                          </div>
                        </label>
                      ))}
                    </div>
                  )}

                  <div className="mt-8 flex gap-3">
                    <Button type="button" variant="ghost" onClick={() => setStep('review')} className="flex-1">
                      Back
                    </Button>
                    <Button
                      type="button"
                      onClick={continueToPreview}
                      disabled={!selectedTemplateId || loading}
                      className="flex-1"
                    >
                      {loading ? 'Loading...' : 'Preview Email'}
                    </Button>
                  </div>
                </div>
              )}

              {/* STEP 4: Email Preview */}
              {step === 'preview' && preview && (
                <div className="space-y-6">
                  <div>
                    <h3 className="text-lg font-semibold text-latte mb-2">Email Preview</h3>
                    <p className="text-sm text-latte/70">Review how the email will look with filled placeholders</p>
                  </div>

                  <div className="bg-[#1a1410] border border-caramel/25 p-4 rounded space-y-3">
                    <div>
                      <div className="text-xs font-medium text-latte/60 mb-1">Subject</div>
                      <div className="text-latte">{preview.subject}</div>
                    </div>
                    <div className="border-t border-caramel/15 pt-3">
                      <div className="text-xs font-medium text-latte/60 mb-1">Body Preview</div>
                      <div className="text-sm text-latte/80 max-h-40 overflow-y-auto">{preview.body.substring(0, 500)}...</div>
                    </div>
                  </div>

                  {preview.unfilled_placeholders.length > 0 && (
                    <div className="p-3 bg-gold/10 border border-gold/25 rounded">
                      <div className="text-sm text-gold">⚠️ Missing data</div>
                      <div className="text-xs text-gold/70 mt-1">
                        These placeholders will not be filled: {preview.unfilled_placeholders.join(', ')}
                      </div>
                      <div className="text-xs text-gold/60 mt-1">
                        They will appear as [placeholder_name] in the email.
                      </div>
                    </div>
                  )}

                  <div className="mt-8 flex gap-3">
                    <Button type="button" variant="ghost" onClick={() => setStep('template')} className="flex-1">
                      Back
                    </Button>
                    <Button
                      type="button"
                      onClick={() => setStep('mode-select')}
                      className="flex-1"
                    >
                      Continue to Sending Mode
                    </Button>
                  </div>
                </div>
              )}

              {/* STEP 5: Sending Mode */}
              {step === 'mode-select' && review && (
                <div className="space-y-6">
                  <div>
                    <h3 className="text-lg font-semibold text-latte mb-2">Choose Sending Preferences</h3>
                    <p className="text-sm text-latte/70">Select how you want to send these emails</p>
                  </div>

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

                  <div className="mt-8 flex gap-3">
                    <Button type="button" variant="ghost" onClick={() => setStep('preview')} className="flex-1">
                      Back
                    </Button>
                    <Button
                      type="button"
                      onClick={executeResend}
                      disabled={sending}
                      className="flex-1"
                    >
                      {sending ? 'Queuing...' : 'Confirm & Queue'}
                    </Button>
                  </div>
                </div>
              )}

              {/* STEP 6: Complete */}
              {step === 'sending' && result && (
                <div className="space-y-6">
                  <div className="bg-gold/10 border border-gold/25 p-4 rounded">
                    <div className="font-semibold text-gold">Resend Campaign Queued Successfully</div>
                    {result.campaign_name && (
                      <div className="text-sm text-latte/70 mt-2">
                        Campaign: <span className="text-latte font-medium">{result.campaign_name}</span>
                      </div>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-3">
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

                  <Button type="button" onClick={closeModal} className="w-full">
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
