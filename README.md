# BeviGrow AI Outreach Automation

Researches coffee buyers, finds the right contact, writes a personalised email
from your approved template, waits for your approval, sends it through your own
Gmail, and logs everything in the BeviGrow tracker.

Nothing is ever sent without you pressing **a** for approve.

---

## 1. What you need to provide

| # | What | Where it goes | Needed for |
|---|------|---------------|-----------|
| 1 | Your **approved email sample** | `config/email_template.md` | the real wording |
| 2 | Your **name, job title, phone, website** | `.env` (`SENDER_*`) | your signature |
| 3 | **BeviGrow tracker login** (the email + password you use on the tracker website) | `.env` (`BEVIGROW_EMAIL`, `BEVIGROW_PASSWORD`) | logging outreach |
| 4 | **Gmail OAuth client file** from Google Cloud Console | `config/gmail_credentials.json` | sending email |
| 5 | **Anthropic API key** (optional but strongly recommended) | `.env` (`ANTHROPIC_API_KEY`) | real research + personalisation |
| 6 | **Tavily API key** (optional) | `.env` (`TAVILY_API_KEY`) | more reliable website discovery |
| 7 | Your **company list** | `data/companies.csv` (or .xlsx) | the prospects |

Steps 3–5 are handled for you by `setup` — you just answer the questions.
Steps 1–4 are required. 5 and 6 are optional; without them the system still
works, but it uses keyword rules instead of real reasoning.

`data/companies.csv` already contains **37 real European green coffee
importers, traders and specialty roasters** as a starting list — Hamburg and
Antwerp trading houses, Nordic importers, UK importers, and specialty roasters
who source their own green. Replace it with your own list whenever you have one.

---

## 2. First-time setup

Everything runs inside `.venv`, which is already created. Open a terminal in
this folder and use `.venv\Scripts\python.exe` as your Python.

```powershell
# 1. install (already done once, repeat only if you change requirements.txt)
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. answer a few questions - this writes your .env for you
.venv\Scripts\python.exe -m src.main setup

# 3. check what is configured and what is missing
.venv\Scripts\python.exe -m src.main check
```

**You never have to edit a configuration file by hand.** `setup` asks one
question at a time, explains each one, hides passwords while you type, and then
immediately tests your tracker login, your Claude key and your search key so
that any mistake shows up straight away.

`check` prints a table telling you exactly what is still missing.

### Setting up Gmail (one time)

1. Go to <https://console.cloud.google.com/> and create a project (any name).
2. **APIs & Services → Library** → search "Gmail API" → **Enable**.
3. **APIs & Services → OAuth consent screen** → External → fill in the app name
   and your email → add yourself as a **Test user**.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID →
   Desktop app** → **Download JSON**.
5. Save that file as `config\gmail_credentials.json` in this folder.
6. Run:

```powershell
.venv\Scripts\python.exe -m src.main auth-gmail
```

A browser opens once. Approve it. A token is stored in `config\gmail_token.json`
and your password is never seen or stored.

---

## 3. Your first test (safe)

`.env` ships with `TEST_MODE=true`, so nothing can leave your computer.

```powershell
# research one company only - never prepares or sends anything
.venv\Scripts\python.exe -m src.main research --company "Some Coffee Importer" --country Germany

# the full pipeline for ONE company, with approval, still simulated
.venv\Scripts\python.exe -m src.main run --limit 1
```

You will see the research, the chosen email address, the chosen person, and the
final email. Then: **a**pprove / **e**dit / **s**kip / **q**uit.

Approving in test mode writes the complete message to `data\outbox\` so you can
read exactly what would have been sent.

---

## 4. Going live

Only after a test looks right. In `.env` change **both**:

```
TEST_MODE=false
ALLOW_REAL_SENDING=true
```

Two separate switches means you cannot send by accident. `REQUIRE_APPROVAL=true`
still applies, so every message is shown to you first.

```powershell
.venv\Scripts\python.exe -m src.main run --limit 1     # one real email
.venv\Scripts\python.exe -m src.main run --limit 10    # a batch of ten
```

---

## 5. Everyday commands

| Command | What it does |
|---------|--------------|
| `setup` | asks a few questions and writes your `.env` for you |
| `check` | what is configured, what is missing, current safety settings |
| `auth-gmail` | one-time Gmail authorisation |
| `research --company "X"` | research only, sends nothing |
| `run --limit 5` | the full pipeline for 5 companies, with approval |
| `followups` | what is due for a follow-up |
| `followups --send` | prepare and send follow-ups (still with approval) |
| `replies --days 30` | read Gmail replies and update tracker statuses |
| `linkedin` | the manual LinkedIn task list |
| `linkedin-done "Company"` | record that you sent a LinkedIn message |
| `tracker` / `tracker --list` | statistics and records from the BeviGrow tracker |
| `report` | summary of every company processed so far |

Add `-v` to any command for detailed logging.

---

## 6. Your company list

`data\companies.csv` — minimum columns **Company, City, Country**;
optional **Website, Notes**.

Excel (`.xlsx`) works too. Column names are matched loosely, so `Company name`,
`Firma` and `Name` are all understood.

A plain text file with one company per line also works:

```
Benecke Coffee GmbH & Co. KG - Hamburg, Germany
```

---

## 7. Your email template

`config\email_template.md` is the source of truth. **Replace the placeholder
text with your own approved sample.** The system never rewrites it — it only
fills in these:

```
{{salutation}}          Dear Mr Schmidt,  /  Dear Benecke Coffee team,
{{context_sentence}}    ONE researched sentence, or empty - never invented
{{company_name}}        the prospect
{{contact_first_name}}  first name, empty if nobody was verified
{{sender_name}} {{sender_title}} {{sender_company}}
{{sender_phone}} {{sender_email}} {{sender_website}} {{sender_location}}
```

Three more templates work the same way: `followup_template.md`,
`website_enquiry_template.md`, `linkedin_templates.md`.

---

## 8. How it decides things

**Which email address** — every address found is scored. Purchasing, green
coffee, sourcing and buying desks win; HR, support and press are avoided; an
address belonging to a verified Green Coffee Buyer beats a generic `info@`.
If two addresses are equally plausible the company is flagged for your review
rather than guessed at.

**Which person** — Owner, Founder, MD, Purchasing/Green Coffee Buyer, Sourcing
and Import Manager, in that order. A person is only used if their name was
actually published. Names are never invented; when none is found the email
addresses the company.

**Relevance** — HIGH / MEDIUM / LOW / IRRELEVANT / UNCERTAIN with a reason.
Thin information means UNCERTAIN and a flag for you, never a rejection.

**Duplicates** — checked twice: a local log, and the BeviGrow tracker itself
(by company name, website domain and email). Inside `DUPLICATE_COOLDOWN_DAYS`
you get "Already contacted — review existing record" and nothing is sent.

**LinkedIn** — never automated. URLs and personalised text are prepared in
`data\results\linkedin_tasks.md` for you to send by hand. A personal profile is
only used when its name matches the person you are writing to, otherwise the
company page is used and the message addresses the company.

**Contact forms** — used only when no suitable email exists. You see the filled
form before it is submitted. If a CAPTCHA appears the system stops and asks you
to finish it. Needs one extra install:

```powershell
.venv\Scripts\python.exe -m playwright install chromium
```

---

## 9. The BeviGrow tracker integration

Discovered from your live app — this is a real API integration, no browser
automation.

```
Base      https://bevigrow-backend-dkay.onrender.com
Login     POST /api/auth/login   {"email": ..., "password": ...} -> access_token
Auth      Authorization: Bearer <access_token>
Create    POST  /api/outreach                          -> 201
Read      GET   /api/outreach?search=&status=&due=true
Update    PATCH /api/outreach/{id}
Follow-up POST  /api/outreach/{id}/follow-up?days_until_next=N
Stats     GET   /api/outreach/stats
```

Field mapping (tracker form label → API field):

| Tracker form | API field |
|---|---|
| Company | `company_name` |
| Contact person | `contact_person` |
| Website | `website` |
| Country | `country` |
| Channel | `contact_method` (`email`, `linkedin`, `website_form`, `instagram`, `phone`, `whatsapp`, `other`) |
| Exact place | `contact_point` (inbox / LinkedIn URL / form URL) |
| Email | `email` |
| Date contacted | `contacted_on` |
| Message we sent | `message_sent` — the **exact** text that was sent |
| Their reply | `their_reply` |
| Status | `status` (`waiting_reply`, `replied`, `follow_up_needed`, `follow_up_sent`, `no_response`, `not_interested`) |
| Date they replied | `replied_on` |
| Our next action | `next_action` |
| Next follow-up date | `next_follow_up` |
| Notes / memory | `notes` |

---

## 10. Where things are saved

```
data\results\    research-*.json, result-*.json, linkedin_tasks.md
data\outbox\     the exact text of every message (sent or simulated)
data\logs\       one log file per day
data\state\      local duplicate log and the cached tracker token
data\cache\      crawled pages (so re-runs are fast and polite)
```

---

## 11. Safety settings (`.env`)

| Setting | Default | Meaning |
|---|---|---|
| `TEST_MODE` | `true` | nothing can be sent |
| `ALLOW_REAL_SENDING` | `false` | second brake; both must be released to send |
| `REQUIRE_APPROVAL` | `true` | every message shown to you first |
| `MAX_COMPANIES_PER_RUN` | `1` | batch size when `--limit` is not given |
| `DAILY_SEND_LIMIT` | `25` | hard stop per day |
| `SEND_RATE_LIMIT_SECONDS` | `45` | minimum gap between sends |
| `FOLLOW_UP_DAYS` | `7` | when a follow-up becomes due |
| `DUPLICATE_COOLDOWN_DAYS` | `90` | do not re-contact within this window |

Secrets live only in `.env` and `config\gmail_*.json`. Both are in `.gitignore`
and are scrubbed out of every log line.

---

## 12. Outcomes you will see

`SUCCESS` · `SIMULATED` · `NEEDS_REVIEW` · `ALREADY_CONTACTED` · `NO_EMAIL` ·
`FORM_REQUIRED` · `LINKEDIN_MANUAL` · `IRRELEVANT` · `SKIPPED` · `FAILED`

Each one always comes with a reason. Nothing fails silently.

---

## 13. Tests

```powershell
.venv\Scripts\python.exe -m pytest -q
```
