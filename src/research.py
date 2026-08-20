"""
Company research - the orchestrator.

    company name  ->  official website
                  ->  crawl their own site (facts with source URLs)
                  ->  Claude reads the web + the crawled text
                  ->  emails scored, people ranked, relevance classified
                  ->  ResearchResult

Nothing here sends anything. It is safe to run at any time, in any mode.
"""

from __future__ import annotations

from src.config import RESULTS_DIR, settings
from src.crawler import SiteEvidence, crawl_site
from src.email_finder import score_emails
from src.logging_setup import get_logger
from src.models import CompanyInput, PersonCandidate, Priority, ResearchResult
from src.utils import domain_of, normalise_url, slugify, write_json
from src import contact_research, llm, relevance as relevance_mod, search as search_mod

log = get_logger("research")


def _resolve_website(company: CompanyInput, result: ResearchResult) -> None:
    """Step 1: work out the official website."""
    if company.website:
        result.website = normalise_url(company.website)
        result.website_source = "provided in the input file"
        return

    url, source, how = search_mod.find_official_website(
        company.company, company.city, company.country
    )
    if url:
        result.website = url
        result.website_source = how
        result.add_evidence(url, source, how)
    else:
        result.warnings.append("Could not confidently identify an official website.")


def _apply_site_evidence(result: ResearchResult, site: SiteEvidence) -> None:
    """Step 2: fold the crawl results into the record."""
    result.pages_crawled = [p.url for p in site.pages]

    if not site.reachable:
        result.warnings.append(f"Website could not be read ({site.error or 'unknown error'}).")
        return

    if site.base_url and site.base_url != result.website:
        result.website = site.base_url

    result.description = result.description or site.meta_description or site.title
    result.contact_page_url = site.contact_page_url
    if site.form_pages:
        result.contact_form_url = site.form_pages[0]
    if site.phones:
        result.phone = next(iter(site.phones))

    for url in site.linkedin_urls:
        low = url.lower()
        if "/company/" in low and not result.linkedin_company_url:
            result.linkedin_company_url = url
            result.add_evidence(url, site.linkedin_urls[url], "LinkedIn link on their website")
        elif "/in/" in low:
            # Keep every personal profile we saw. Which one (if any) belongs to
            # the person we address is decided later, by name matching.
            if url not in result.linkedin_profiles:
                result.linkedin_profiles.append(url)
                result.add_evidence(url, site.linkedin_urls[url],
                                    "LinkedIn profile on their website")
    if result.linkedin_profiles and not result.linkedin_person_url:
        result.linkedin_person_url = result.linkedin_profiles[0]

    for address, source_url in site.emails.items():
        result.add_evidence(address, source_url, "published on their website")


def _apply_llm_facts(result: ResearchResult, facts: dict, site: SiteEvidence) -> None:
    """Step 3: fold Claude's structured record in - but never let it invent."""
    if not result.website and facts.get("official_website"):
        result.website = normalise_url(facts["official_website"])
        result.website_source = "identified by Claude web research"

    result.country = result.country or (facts.get("country") or "").strip()
    result.city = result.city or (facts.get("city") or "").strip()
    if facts.get("description"):
        result.description = facts["description"].strip()

    if facts.get("linkedin_company_url") and not result.linkedin_company_url:
        url = facts["linkedin_company_url"].strip()
        if "linkedin.com/company/" in url.lower():
            result.linkedin_company_url = url.split("?")[0]

    if facts.get("contact_page_url") and not result.contact_page_url:
        result.contact_page_url = facts["contact_page_url"].strip()

    for flag in facts.get("uncertain_flags") or []:
        if isinstance(flag, str) and flag.strip():
            result.warnings.append(flag.strip())

    # People: only ones Claude reported WITH a source, plus the regex pass.
    llm_people = contact_research.people_from_llm(facts.get("contact_people") or [])
    page_people = contact_research.people_from_pages(
        [(p.url, p.text) for p in site.pages if p.text]
    )
    result.people = contact_research.merge_people(llm_people, page_people)

    # An email Claude reports is only accepted if we also saw it on the site,
    # otherwise it could be a construction. This is the anti-hallucination gate.
    best = (facts.get("best_email") or "").strip().lower()
    if best and best not in site.emails:
        result.warnings.append(
            f"Claude suggested {best} but it was not found published on the website - ignored."
        )


def _attach_person_emails(result: ResearchResult) -> None:
    """
    Link a person to an address that is obviously theirs (anna@ / a.laine@),
    then promote that address: an email belonging to a verified Green Coffee
    Buyer is worth far more than a generic info@ inbox.
    """
    by_address = {e.address: e for e in result.emails}

    for person in result.people:
        first = person.first_name.lower()
        last = person.name.split()[-1].lower() if person.name else ""
        if not first or not last:
            continue

        match = person.email if person.email in by_address else ""
        if not match:
            wanted = {first, last, f"{first}.{last}", f"{first[0]}.{last}",
                      f"{first}{last}", f"{first[0]}{last}", f"{last}.{first}"}
            for address in by_address:
                if address.split("@")[0].lower() in wanted:
                    match = address
                    break

        if not match:
            continue

        person.email = match
        candidate = by_address[match]
        if not candidate.domain_matches_website:
            # An address on someone else's domain stays penalised, however
            # senior the person looks - it may not belong to this company.
            person.reason += "; note: their address is on a different domain"
            continue
        # The person's role decides how good this address is.
        boosted = max(candidate.score, min(person.score, 100) + 15)
        if boosted > candidate.score:
            candidate.score = boosted
            candidate.category = "person"
            title = f" ({person.title})" if person.title else ""
            candidate.reason = (
                f"personal address of {person.name}{title}, published on their website"
            )
        person.reason += "; personal address published on their site"

    result.emails.sort(key=lambda c: (-c.score, c.address))


def research_company(company: CompanyInput, use_llm: bool | None = None,
                     save: bool = True) -> ResearchResult:
    """Research one company end to end. Never raises - failures become warnings."""
    use_llm = llm.available() if use_llm is None else (use_llm and llm.available())

    result = ResearchResult(
        company_input=company,
        resolved_company_name=company.company,
        country=company.country,
        city=company.city,
    )

    log.info("Researching: %s (%s)", company.company, company.location or "location unknown")

    # 1. website ---------------------------------------------------------
    try:
        _resolve_website(company, result)
    except Exception as exc:
        result.warnings.append(f"Website lookup failed: {exc}")

    # 2. crawl -----------------------------------------------------------
    site = SiteEvidence()
    if result.website:
        try:
            site = crawl_site(result.website)
            _apply_site_evidence(result, site)
        except Exception as exc:
            log.exception("Crawl failed for %s", result.website)
            result.warnings.append(f"Crawling the website failed: {exc}")
    else:
        result.warnings.append("No website to crawl.")

    # 3. Claude research -------------------------------------------------
    facts: dict = {}
    if use_llm:
        try:
            result.research_brief = llm.research_company(
                company.company, company.city, company.country, result.website
            )
        except Exception as exc:
            log.warning("Claude web research failed: %s", exc)
            result.warnings.append(f"Claude web research failed: {exc}")

        try:
            facts = llm.extract_facts(
                company=company.company,
                city=company.city,
                country=company.country,
                research_brief=result.research_brief,
                website=result.website,
                site_text=site.combined_text(),
                found_emails=site.emails,
                found_linkedin=site.linkedin_urls,
            )
        except Exception as exc:
            log.warning("Claude extraction failed: %s", exc)
            result.warnings.append(f"Claude extraction failed: {exc}")
    else:
        result.warnings.append(
            "Claude was not used (no ANTHROPIC_API_KEY) - relevance and personalisation "
            "fall back to simple keyword rules."
        )

    # 4. emails ----------------------------------------------------------
    result.emails = score_emails(site.emails, result.website, check_mx=True)

    # 5. people ----------------------------------------------------------
    if facts:
        _apply_llm_facts(result, facts, site)
    else:
        result.people = contact_research.people_from_pages(
            [(p.url, p.text) for p in site.pages if p.text]
        )
    _attach_person_emails(result)

    # 6. LinkedIn fallback ----------------------------------------------
    if not result.linkedin_company_url:
        try:
            found = search_mod.find_linkedin(company.company, result.country or company.country)
            if found:
                result.linkedin_company_url = found
                result.add_evidence(found, found, "web search")
        except Exception as exc:
            log.debug("LinkedIn search failed: %s", exc)

    # 7. relevance -------------------------------------------------------
    rules = relevance_mod.rule_based(site.combined_text(8000), company.company)
    llm_verdict = relevance_mod.from_llm(facts) if facts else None
    result.relevance = relevance_mod.combine(rules, llm_verdict)

    if not result.website and result.relevance.priority is not Priority.IRRELEVANT:
        result.relevance = relevance_mod.Relevance(
            priority=Priority.UNCERTAIN,
            reason="No official website could be verified, so the company could not be assessed.",
            signals=result.relevance.signals,
        )

    result.country = result.country or domain_country_guess(result.website)

    if save:
        path = RESULTS_DIR / f"research-{slugify(company.company)}.json"
        write_json(path, result.to_dict())
        log.debug("Research saved to %s", path)

    log.info(
        "  -> %s | %s | %d emails | %d people | %s",
        result.website or "no website",
        result.relevance.priority.value,
        len(result.emails),
        len(result.people),
        result.primary_email.address if result.primary_email else "no email",
    )
    return result


# Country-code TLD -> country, used only as a last resort for the tracker field.
_CCTLD = {
    "de": "Germany", "at": "Austria", "ch": "Switzerland", "nl": "Netherlands",
    "be": "Belgium", "fr": "France", "it": "Italy", "es": "Spain", "pt": "Portugal",
    "fi": "Finland", "se": "Sweden", "no": "Norway", "dk": "Denmark", "is": "Iceland",
    "pl": "Poland", "cz": "Czechia", "sk": "Slovakia", "hu": "Hungary", "ro": "Romania",
    "gr": "Greece", "ie": "Ireland", "uk": "United Kingdom", "co.uk": "United Kingdom",
    "ee": "Estonia", "lv": "Latvia", "lt": "Lithuania", "si": "Slovenia", "hr": "Croatia",
    "bg": "Bulgaria", "ru": "Russia", "ua": "Ukraine", "tr": "Turkey", "ae": "UAE",
    "au": "Australia", "nz": "New Zealand", "ca": "Canada", "jp": "Japan",
    "kr": "South Korea", "sg": "Singapore", "za": "South Africa", "in": "India",
}


def domain_country_guess(website: str) -> str:
    domain = domain_of(website)
    if not domain:
        return ""
    for suffix, country in sorted(_CCTLD.items(), key=lambda kv: -len(kv[0])):
        if domain.endswith("." + suffix):
            return country
    return ""


def best_person(result: ResearchResult) -> PersonCandidate | None:
    """The person we would address, or None if nobody was verified."""
    for person in result.people:
        if person.score >= 40:
            return person
    return result.people[0] if result.people else None
