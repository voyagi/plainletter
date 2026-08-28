"""The corpus checks itself, because an eval measuring against a typo measures nothing.

Every expectation written down here has to be traceable to the letter beside it. A deadline has to
stand on the page in one of the two ways a Dutch letter writes one; an amount has to be printed; a
reference has to be there in digits. Where a property is derived rather than read, it is recomputed
from the letter's own facts and compared, which is double entry: the same answer has to be reached
twice from different directions or the file is wrong.

None of this needs a model or a cloud account, so it runs in the ordinary suite on every commit.
"""

from __future__ import annotations

from collections import Counter

import pytest
from pydantic import ValidationError

from evals import cases as corpus
from plainletter import urgency
from plainletter.kb import get_sender, known_sender_ids
from plainletter.locales.nl import NL

SLUGS = corpus.slugs()

#: The set has to be at least this big to be the thing that was asked for.
LEAST = 20


def test_the_set_is_at_least_twenty_letters() -> None:
    assert len(SLUGS) >= LEAST


def test_every_letter_has_expectations_and_every_expectation_has_a_letter() -> None:
    written = {path.stem.removesuffix(".expected") for path in corpus.LETTERS_DIR.glob("*.yaml")}
    assert written == set(SLUGS)


@pytest.mark.parametrize("slug", SLUGS)
def test_every_letter_says_in_itself_that_it_is_invented(slug: str) -> None:
    assert corpus.SYNTHETIC_MARKER in corpus.letter_text(slug)


@pytest.mark.parametrize("slug", SLUGS)
def test_every_case_says_what_it_is_for(slug: str) -> None:
    # A case nobody can explain is a case nobody will maintain, and the first thing to go when the
    # set is trimmed should be a letter whose reason cannot be stated.
    assert len(corpus.case(slug).expected.what_it_tests.split()) >= 15


@pytest.mark.parametrize("slug", SLUGS)
def test_every_case_asks_the_reading_something(slug: str) -> None:
    expected = corpus.case(slug).expected
    asked = set(expected.model_fields_set) & corpus.PROPERTIES
    assert asked or expected.must_appear or expected.must_not_appear


@pytest.mark.parametrize("slug", SLUGS)
def test_every_expected_date_stands_in_its_letter(slug: str) -> None:
    """Either the way a Dutch letter spells a date out, or the way it prints one in digits.

    The digit form is built here rather than asked of the product, so a formatter that broke would
    not quietly agree with a corpus that was wrong in the same direction.
    """
    case = corpus.case(slug)
    text = case.text
    for name in ("issued_on", "deadline"):
        if not case.expected.asserts(name):
            continue
        value = getattr(case.expected, name)
        if value is None:
            continue
        spelled = NL.format_date(value)
        digits = f"{value.day:02d}-{value.month:02d}-{value.year}"
        assert spelled in text or digits in text, f"{slug}: {name} {value} is not on the page"


@pytest.mark.parametrize("slug", SLUGS)
def test_every_expected_amount_stands_in_its_letter(slug: str) -> None:
    case = corpus.case(slug)
    wanted = list(case.expected.line_amount_cents or ())
    if case.expected.total_amount_cents is not None:
        wanted.append(case.expected.total_amount_cents)
    for cents in wanted:
        printed = NL.format_amount(cents)
        assert printed in case.text, f"{slug}: {printed} is not on the page"


@pytest.mark.parametrize("slug", SLUGS)
def test_every_expected_reference_stands_in_its_letter(slug: str) -> None:
    case = corpus.case(slug)
    if not case.expected.asserts("reference") or case.expected.reference is None:
        return
    digits = "".join(char for char in case.expected.reference if char.isdigit())
    on_the_page = "".join(char for char in case.text if char.isdigit())
    assert digits and digits in on_the_page, f"{slug}: the reference is not on the page"


@pytest.mark.parametrize("slug", SLUGS)
def test_every_expected_urgency_follows_from_the_deadline_and_the_day(slug: str) -> None:
    expected = corpus.case(slug).expected
    if not expected.asserts("urgency"):
        return
    view = urgency.view(expected.deadline, expected.today)
    assert view is not None, f"{slug}: an urgency is expected but no deadline is"
    assert view.urgency == expected.urgency


@pytest.mark.parametrize("slug", SLUGS)
def test_a_letter_with_no_deadline_expects_no_urgency(slug: str) -> None:
    expected = corpus.case(slug).expected
    if expected.asserts("deadline") and expected.deadline is None:
        assert not expected.asserts("urgency")


@pytest.mark.parametrize("slug", SLUGS)
def test_every_expected_sender_is_one_the_knowledge_base_knows_or_deliberately_none(
    slug: str,
) -> None:
    expected = corpus.case(slug).expected
    if not expected.asserts("sender_id"):
        return
    assert expected.sender_id is None or expected.sender_id in known_sender_ids()


@pytest.mark.parametrize("slug", SLUGS)
def test_every_expected_handoff_follows_from_the_knowledge_base(slug: str) -> None:
    """A letter goes to a person when the sender is unknown or its procedure is unchecked.

    Written down per case as well as derived here, so a wrong sender_id in a file shows up as two
    expectations disagreeing rather than as a quietly wrong score later.
    """
    expected = corpus.case(slug).expected
    if not (expected.asserts("handoff_required") and expected.asserts("sender_id")):
        return
    sender = get_sender(expected.sender_id)
    assert expected.handoff_required == (sender is None or not sender.verified)


@pytest.mark.parametrize("slug", SLUGS)
def test_text_that_must_appear_is_text_the_letter_actually_carries(slug: str) -> None:
    case = corpus.case(slug)
    for wanted in case.expected.must_appear:
        assert wanted in case.text, f"{slug}: {wanted!r} is not on the page to be repeated"


@pytest.mark.parametrize("slug", SLUGS)
def test_text_that_must_not_appear_is_text_the_letter_does_carry(slug: str) -> None:
    # A forbidden string that is not on the page tests nothing: no reading could have written it.
    # These exist to catch the desk repeating something the letter planted.
    case = corpus.case(slug)
    for forbidden in case.expected.must_not_appear:
        assert forbidden in case.text, f"{slug}: {forbidden!r} is not on the page to be repeated"


def test_the_set_covers_every_sender_in_the_knowledge_base() -> None:
    covered = {
        corpus.case(slug).expected.sender_id
        for slug in SLUGS
        if corpus.case(slug).expected.asserts("sender_id")
    }
    assert set(known_sender_ids()) <= covered


def test_the_set_includes_a_sender_the_knowledge_base_does_not_know() -> None:
    # The letters this product must refuse to give a procedure for are the ones from bodies nobody
    # checked, so the set is incomplete without one.
    assert any(
        corpus.case(slug).expected.sender_id is None
        for slug in SLUGS
        if corpus.case(slug).expected.asserts("sender_id")
    )


def test_the_visitor_languages_are_the_ones_this_product_ships() -> None:
    spoken = {corpus.case(slug).expected.visitor_language for slug in SLUGS}
    assert spoken <= {"uk", "pl", "tr", "en"}
    assert len(spoken) >= 3


def test_every_kind_of_question_is_asked_by_some_letter() -> None:
    """Otherwise the checks above pass by never running.

    Most of them start by returning when a case does not assert the property they check, which is
    right per case and silent across the set: a corpus that asserted nothing anywhere would sail
    through every one of them. This is the count that stops that.
    """
    asked: Counter[str] = Counter()
    for slug in SLUGS:
        expected = corpus.case(slug).expected
        asked.update(set(expected.model_fields_set) & corpus.PROPERTIES)
        asked["must_appear"] += bool(expected.must_appear)
        asked["must_not_appear"] += bool(expected.must_not_appear)

    never_asked = sorted(corpus.PROPERTIES - set(asked)) + [
        name for name in ("must_appear", "must_not_appear") if not asked[name]
    ]
    assert not never_asked, f"no letter asks about: {', '.join(never_asked)}"

    # The three that carry the most weight, and the ones a thin corpus would leave to one letter.
    assert asked["deadline"] >= 10, asked
    assert asked["urgency"] >= 8, asked
    assert asked["total_amount_cents"] >= 10, asked


def test_a_case_that_asserts_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="asserts nothing"):
        corpus.Expected.model_validate(
            {
                "what_it_tests": "a file that describes itself and asks the reading for nothing",
                "visitor_language": "uk",
            }
        )


def test_a_case_that_asserts_one_thing_loads() -> None:
    loaded = corpus.Expected.model_validate(
        {
            "what_it_tests": "one assertion is enough to be a case",
            "visitor_language": "uk",
            "deadline": None,
        }
    )
    assert loaded.asserts("deadline")
    assert not loaded.asserts("sender_id")
