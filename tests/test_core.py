"""
Tests for the parts that must never break: email selection, duplicate keys,
template rendering, and the tracker payload mapping.

Run:  python -m pytest -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.email_finder import score_emails, select_recipients, notes_for_tracker  # noqa: E402
from src.email_generator import render  # noqa: E402
from src.input_loader import _split_freeform  # noqa: E402
from src.models import Channel, CompanyInput, PreparedMessage, Priority, Relevance, ResearchResult  # noqa: E402
from src.relevance import rule_based  # noqa: E402
from src.tracker import build_notes, build_outreach_payload  # noqa: E402
from src.utils import (  # noqa: E402
    company_key,
    deobfuscate,
    domain_of,
    extract_emails,
    looks_like_email,
    normalise_company_name,
    normalise_url,
    similar,
)


# --------------------------------------------------------------------------
# utils
# --------------------------------------------------------------------------
def test_company_name_normalisation():
    assert normalise_company_name("Benecke Coffee GmbH & Co. KG") == "benecke coffee"
    assert normalise_company_name("Benecke Coffee") == "benecke coffee"
    assert company_key("Benecke Coffee GmbH & Co. KG") == "benecke-coffee"


def test_similarity_matches_legal_suffix_variants():
    assert similar("Benecke Coffee GmbH & Co. KG", "Benecke Coffee") >= 0.9
    assert similar("Benecke Coffee", "Nordic Roasters AB") < 0.3


def test_domain_extraction():
    assert domain_of("https://www.example.com/contact") == "example.com"
    assert domain_of("info@Example.COM") == "example.com"
    assert domain_of("") == ""


def test_url_normalisation():
    assert normalise_url("example.com") == "https://example.com"
    assert normalise_url("https://example.com/") == "https://example.com"


@pytest.mark.parametrize(
    "address,valid",
    [
        ("info@company.com", True),
        ("purchasing@coffee-import.de", True),
        ("not-an-email", False),
        ("a@b", False),
        ("noreply@company.com", False),
        ("logo@2x.png", False),
    ],
)
def test_email_validation(address, valid):
    assert looks_like_email(address) is valid


def test_deobfuscated_emails_are_recovered():
    text = "Write to info (at) benecke-coffee (dot) de for enquiries"
    assert "info@benecke-coffee.de" in extract_emails(deobfuscate(text))


# --------------------------------------------------------------------------
# input parsing
# --------------------------------------------------------------------------
def test_freeform_line_parsing():
    parsed = _split_freeform("Benecke Coffee GmbH & Co. KG - Hamburg, Germany")
    assert parsed.company == "Benecke Coffee GmbH & Co. KG"
    assert parsed.city == "Hamburg"
    assert parsed.country == "Germany"


# --------------------------------------------------------------------------
# email selection - the rules from the brief
# --------------------------------------------------------------------------
def _score(emails: dict[str, str], site="https://coffee.de"):
    return score_emails(emails, site, check_mx=False)


def test_purchasing_beats_general_inbox():
    candidates = _score(
        {
            "info@coffee.de": "https://coffee.de/contact",
            "einkauf@coffee.de": "https://coffee.de/contact",
        }
    )
    assert candidates[0].address == "einkauf@coffee.de"
    assert candidates[0].category == "purchasing"


def test_hr_and_support_are_avoided():
    candidates = _score(
        {
            "jobs@coffee.de": "https://coffee.de/jobs",
            "info@coffee.de": "https://coffee.de/contact",
        }
    )
    assert candidates[0].address == "info@coffee.de"
    assert [c for c in candidates if c.address == "jobs@coffee.de"][0].category == "avoid"


def test_green_coffee_desk_wins_everything():
    candidates = _score(
        {
            "greencoffee@coffee.de": "https://coffee.de/green",
            "einkauf@coffee.de": "https://coffee.de/contact",
            "sales@coffee.de": "https://coffee.de/contact",
        }
    )
    assert candidates[0].address == "greencoffee@coffee.de"


def test_only_hr_address_is_flagged_for_review():
    candidates = _score({"hr@coffee.de": "https://coffee.de/jobs"})
    to, cc, reason, needs_review = select_recipients(candidates)
    assert needs_review is True
    assert "avoid" in reason or "weak" in reason.lower()


def test_no_addresses_needs_review():
    to, cc, reason, needs_review = select_recipients([])
    assert to == []
    assert needs_review is True


def test_two_different_relevant_desks_can_produce_a_cc():
    candidates = _score(
        {
            "einkauf@coffee.de": "https://coffee.de/contact",
            "geschaeftsfuehrung@coffee.de": "https://coffee.de/team",
        }
    )
    to, cc, _, _ = select_recipients(candidates)
    assert to == ["einkauf@coffee.de"]
    assert cc == ["geschaeftsfuehrung@coffee.de"]


def test_off_domain_address_is_penalised():
    candidates = _score({"info@somewhere-else.com": "https://coffee.de/contact"})
    assert candidates[0].domain_matches_website is False
    assert "different domain" in candidates[0].reason


def test_tracker_notes_list_all_relevant_addresses():
    candidates = _score(
        {"purchasing@coffee.de": "u", "info@coffee.de": "u", "jobs@coffee.de": "u"}
    )
    notes = notes_for_tracker(candidates)
    assert "purchasing@coffee.de" in notes
    assert "info@coffee.de" in notes
    assert "jobs@coffee.de" not in notes


# --------------------------------------------------------------------------
# relevance
# --------------------------------------------------------------------------
def test_green_coffee_importer_scores_high():
    text = ("We are a green coffee importer in Hamburg. We import Robusta and Arabica "
            "for European roasters and hold stock in our warehouse.")
    verdict = rule_based(text, "Benecke Coffee")
    assert verdict.priority in (Priority.HIGH, Priority.MEDIUM)


def test_non_coffee_business_is_uncertain_not_rejected():
    verdict = rule_based("We manufacture industrial valves.", "Valve Co")
    assert verdict.priority is Priority.UNCERTAIN


def test_thin_information_is_never_rejected():
    verdict = rule_based("", "Unknown Ltd")
    assert verdict.priority is Priority.UNCERTAIN


# --------------------------------------------------------------------------
# templates
# --------------------------------------------------------------------------
def test_render_substitutes_and_leaves_no_placeholders():
    out = render("Hello {{company_name}}, {{context_sentence}}Regards",
                 {"company_name": "Acme", "context_sentence": ""})
    assert "Acme" in out
    assert "{{" not in out


def test_real_templates_are_valid():
    from src.email_generator import check_templates

    assert check_templates() == []


# --------------------------------------------------------------------------
# tracker payload mapping
# --------------------------------------------------------------------------
def _research() -> ResearchResult:
    return ResearchResult(
        company_input=CompanyInput(company="Benecke Coffee", country="Germany"),
        resolved_company_name="Benecke Coffee GmbH & Co. KG",
        website="https://benecke-coffee.de",
        country="Germany",
        relevance=Relevance(priority=Priority.HIGH, reason="imports green coffee"),
    )


def test_email_payload_maps_to_the_api_fields():
    message = PreparedMessage(
        channel=Channel.EMAIL,
        to=["einkauf@benecke-coffee.de"],
        cc=["info@benecke-coffee.de"],
        subject="Indian Green Coffee",
        body="Dear team,\n\nHello.\n",
    )
    payload = build_outreach_payload(
        _research(), message, contact_person="Anna Schmidt", contacted_on="2026-08-18"
    )
    assert payload["company_name"] == "Benecke Coffee GmbH & Co. KG"
    assert payload["contact_method"] == "email"
    assert payload["contact_point"] == "einkauf@benecke-coffee.de, info@benecke-coffee.de"
    assert payload["email"] == "einkauf@benecke-coffee.de"
    assert payload["status"] == "waiting_reply"
    assert payload["contacted_on"] == "2026-08-18"
    # The EXACT sent message must be preserved.
    assert "Subject: Indian Green Coffee" in payload["message_sent"]
    assert "Dear team," in payload["message_sent"]


def test_website_form_payload_uses_the_form_url_as_exact_place():
    message = PreparedMessage(
        channel=Channel.WEBSITE_FORM,
        subject="Enquiry",
        body="Hello",
        target_url="https://benecke-coffee.de/kontakt",
    )
    payload = build_outreach_payload(_research(), message)
    assert payload["contact_method"] == "website_form"
    assert payload["contact_point"] == "https://benecke-coffee.de/kontakt"
    assert "email" not in payload or payload["email"] is None


def test_linkedin_payload_uses_the_profile_url_as_exact_place():
    message = PreparedMessage(
        channel=Channel.LINKEDIN,
        body="Hello",
        target_url="https://www.linkedin.com/company/benecke-coffee",
    )
    payload = build_outreach_payload(_research(), message)
    assert payload["contact_method"] == "linkedin"
    assert payload["contact_point"] == "https://www.linkedin.com/company/benecke-coffee"


# --------------------------------------------------------------------------
# LinkedIn targeting - a message addressed to one person must never be
# delivered to a different person's profile.
# --------------------------------------------------------------------------
def test_linkedin_uses_a_profile_only_when_the_name_matches():
    from src.linkedin import pick_target
    from src.models import PersonCandidate

    research = _research()
    research.linkedin_company_url = "https://linkedin.com/company/benecke-coffee"
    research.linkedin_profiles = [
        "https://linkedin.com/in/morten-wennersgaard-06a7047",
        "https://linkedin.com/in/anna-schmidt-1234",
    ]
    url, note = pick_target(research, PersonCandidate(name="Anna Schmidt", score=90))
    assert url == "https://linkedin.com/in/anna-schmidt-1234"
    assert "matched" in note


def test_linkedin_falls_back_to_the_company_page_when_no_profile_matches():
    from src.linkedin import pick_target
    from src.models import PersonCandidate

    research = _research()
    research.linkedin_company_url = "https://linkedin.com/company/benecke-coffee"
    research.linkedin_profiles = ["https://linkedin.com/in/morten-wennersgaard-06a7047"]
    url, note = pick_target(research, PersonCandidate(name="Josh Coleman", score=100))
    assert url == "https://linkedin.com/company/benecke-coffee"
    assert "no LinkedIn profile could be matched" in note


def test_linkedin_returns_nothing_when_there_is_nothing_public():
    from src.linkedin import pick_target

    url, note = pick_target(_research(), None)
    assert url == ""


def test_empty_placeholder_does_not_leave_a_dangling_comma():
    out = render("Hello {{contact_first_name}}, I am {{sender_name}}.",
                 {"contact_first_name": "", "sender_name": "Ravi"})
    assert out.startswith("Hello, I am Ravi.")


def test_notes_are_short_and_useful():
    research = _research()
    notes = build_notes(research, "2 relevant emails identified: a@b.de (purchasing), c@d.de (general).")
    assert "purchasing" in notes
    assert "Relevance: HIGH PRIORITY" in notes
    assert len(notes) < 1800
