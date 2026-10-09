"""Quote verification: tolerant of tidied quotes and page breaks, strict about invented ones."""
from app.enums import Category, MandatoryLevel, Status
from app.schemas import NormalizedRule, Requirement, SourceRef
from app.services import compliance
from app.services.parser import PageChunk
from app.services.quotes import locate_quote

# Real wording from the CFCU tender, including the source's own typo ("in a eligible country").
PAGE1 = ("Participation is open to all natural persons who are nationals of and legal persons which are effectively "
         "established in a Member State of the European Union or in a eligible country or territory as defined "
         "under the Regulation (EU) No. 236/2014. All supplies must originate in one or more of these countries.")
# A sentence that runs across a page break.
PAGE3 = "Furthermore, the data for this third entity for the relevant"
# Each real page starts with the notice's running header, which sits between the two halves of the sentence.
HEADER = ("OJ/S S181 20/09/2018 409192-2018-EN External aid programmes - Supplies - Contract notice - Open procedure "
          "Supplement to the Official Journal of the European Union 4 / 5 https://ted.europa.eu/ TED")
PAGE4 = HEADER + " selection criterion should be included in the tender in a separate document. Proof of the capacity will follow."


def pages(*texts):
    return [PageChunk("d", i + 1, t, "native") for i, t in enumerate(texts)]


def test_exact_quote_is_accepted_unchanged():
    page, excerpt = locate_quote("All supplies must originate in one or more of these countries.", pages(PAGE1))
    assert page.page_number == 1 and excerpt == "All supplies must originate in one or more of these countries."


def test_quote_with_a_tidied_typo_is_accepted_and_cites_the_page_wording():
    tidied = ("which are effectively established in a Member State of the European Union or in an eligible country "
              "or territory as defined under the Regulation (EU) No. 236/2014")
    page, excerpt = locate_quote(tidied, pages(PAGE1))
    assert page.page_number == 1
    assert "in a eligible country" in excerpt  # the stored citation is the tender's own words, typo included
    assert "in an eligible" not in excerpt


def test_quote_across_a_page_break_is_accepted_and_cited_on_one_page():
    quote = ("Furthermore, the data for this third entity for the relevant selection criterion should be included "
             "in the tender in a separate document.")
    page, excerpt = locate_quote(quote, pages(PAGE3, PAGE4))
    assert page.page_number in (1, 2)  # cited on exactly one of the two pages
    from eval.metrics import norm
    assert norm(excerpt) in norm(page.text)  # the excerpt really is on the cited page (citation validity)


def test_invented_or_rewritten_quotes_are_rejected():
    assert locate_quote("Bidders must hold a valid ISO 27001 certificate issued within the last year.", pages(PAGE1)) is None
    assert locate_quote("Participation is restricted to companies registered in Azerbaijan only.", pages(PAGE1)) is None
    # a heavily paraphrased version of a real sentence
    assert locate_quote("Companies from the EU can take part and goods must be made there too.", pages(PAGE1)) is None


def test_scattered_common_words_do_not_count_as_a_match():
    scattered = "Participation is open and supplies must originate and legal persons European Union countries"
    assert locate_quote(scattered, pages(PAGE1)) is None


def test_too_short_quotes_are_not_verified_fuzzily():
    assert locate_quote("or territory", pages(PAGE1)) is not None  # still fine when exact
    assert locate_quote("in an eligible", pages(PAGE1)) is None  # 3 words, not exact: too weak to trust
    assert locate_quote("", pages(PAGE1)) is None


def test_partial_results_use_the_partial_reason_code():
    req = Requirement(requirement_id="R", text="Provide a tender guarantee", category=Category.FINANCIAL,
                      mandatory_level=MandatoryLevel.MANDATORY, normalized_rule=NormalizedRule(),
                      sources=[SourceRef(document_id="d", page=1, excerpt="e")], extraction_confidence=0.9)
    assert compliance.reason_code_for(req, Status.PARTIALLY_MET).value == "MANDATORY_PARTIALLY_MET"
    assert compliance.reason_code_for(req, Status.NOT_MET).value == "FINANCIAL_THRESHOLD_NOT_MET"
    assert compliance.reason_code_for(req, Status.MET) is None
