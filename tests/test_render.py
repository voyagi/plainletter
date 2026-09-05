import re
from datetime import date

from icalendar import Calendar

from plainletter.demo import sample_input, scripted_model
from plainletter.pipeline import Pipeline
from plainletter.render import desk_card_html, is_rtl, reminder_ics
from plainletter.schemas import Explanation

SAMPLE = "cjib-verkeersboete"
LETTER = sample_input(SAMPLE)
TODAY = date(2026, 8, 21)


def _channels(colour: str) -> tuple[int, int, int]:
    bare = colour.lstrip("#")
    if len(bare) == 3:
        bare = "".join(char * 2 for char in bare)
    return int(bare[0:2], 16), int(bare[2:4], 16), int(bare[4:6], 16)


def reading(language: str = "uk"):
    return Pipeline(model=scripted_model(SAMPLE)).run(
        LETTER, visitor_language=language, today=TODAY
    )


def test_the_card_carries_the_deadline_the_days_and_the_posting_date() -> None:
    card = desk_card_html(reading(), TODAY)
    assert "15 september 2026" in card
    assert "Nog 25 dagen" in card
    assert "8 september 2026" in card


def test_the_urgency_state_is_a_word_and_not_only_a_colour() -> None:
    # The card is printed in black and white behind a library counter, so the state has to survive
    # losing every colour on the page.
    assert "Nog tijd" in desk_card_html(reading(), TODAY)


def test_a_right_to_left_visitor_language_sets_the_direction() -> None:
    # No sample letter ships in a right-to-left language, so this drives the renderer directly.
    # The capability has to keep working: the moment one is added, the card must already be right.
    #
    # The explanation has to be substituted rather than only naming "he" as the visitor language.
    # Asking a scripted model that answers in nl and uk for a Hebrew reading gets Dutch back, and
    # a card that tags Dutch as Hebrew would satisfy every assertion below while rendering nothing
    # right-to-left at all.
    hebrew = Explanation(
        language="he",
        what_is_this="מכתב רשמי.",
        by_when="עד 15 בספטמבר 2026.",
        if_you_do_nothing="הסכום יגדל.",
    )
    whole = reading("he")
    card = desk_card_html(
        whole.model_copy(update={"explanations": (*whole.explanations, hebrew)}), TODAY
    )
    assert 'dir="rtl"' in card
    assert 'lang="he"' in card
    assert is_rtl("he") and is_rtl("ar") and is_rtl("fa")
    assert not is_rtl("nl")
    assert not is_rtl("uk")


def test_a_left_to_right_visitor_language_does_not() -> None:
    card = desk_card_html(reading("nl"), TODAY)
    assert 'dir="rtl"' not in card


def test_the_card_prints_the_same_key_the_screen_showed() -> None:
    # One numbering across the screen and the paper is the whole mechanism: the volunteer says
    # "number four" and the visitor finds the same words in a different alphabet.
    card = desk_card_html(reading(), TODAY)
    for key in reading().letter.keys:
        assert f'<span class="n">{key.number}</span>' in card
    assert "Totaal te betalen: EUR 174,00" in card


def test_the_card_shows_the_broken_key_as_an_absence_and_not_as_a_fact() -> None:
    card = desk_card_html(reading(), TODAY)
    assert 'class="broken"' in card
    assert "Vraag de bezoeker het kenteken van de brief voor te lezen." in card


def test_nothing_on_the_card_carries_meaning_in_colour() -> None:
    # It prints on the monochrome printer behind a library counter. A colour that has to survive
    # greyscale is a colour that decides nothing, so the card carries none at all.
    card = desk_card_html(reading(), TODAY)
    colours = re.findall(r"#[0-9a-fA-F]{3,6}", card)
    assert colours
    for colour in colours:
        red, green, blue = _channels(colour)
        assert red == green == blue, f"{colour} is not a grey"


def test_the_reminder_is_a_calendar_a_phone_can_open() -> None:
    ics = reminder_ics(reading(), uid="test@plainletter")
    calendar = Calendar.from_ical(ics)
    events = [item for item in calendar.walk() if item.name == "VEVENT"]
    assert len(events) == 1
    assert events[0]["SUMMARY"].startswith("Centraal Justitieel Incassobureau")
    assert events[0].decoded("DTSTART") == date(2026, 9, 15)
    assert any(item.name == "VALARM" for item in calendar.walk())


def test_the_same_reading_renders_the_same_reminder_twice() -> None:
    first = reminder_ics(reading(), uid="test@plainletter")
    second = reminder_ics(reading(), uid="test@plainletter")
    assert first == second


def test_the_card_masks_exactly_what_the_response_masks() -> None:
    # The runtime walks every string in the response through the mask, the reference and the two
    # strings in the band included. A string left unmasked here is one the printed card shows and
    # the console does not, for the number the visitor has to quote at a counter.
    from plainletter.app import _redacted
    from plainletter.locales.nl import looks_like_bsn

    hidden = next(number for number in ("111222333", "123456782") if looks_like_bsn(number))
    whole = reading()
    facts = whole.facts
    assert facts.reference is not None
    leaky = whole.model_copy(
        update={
            "facts": facts.model_copy(
                update={"reference": facts.reference.model_copy(update={"value": hidden})}
            ),
            "sender_name": f"Incassobureau {hidden}",
            "letter_type": f"Beschikking {hidden}",
        }
    )

    card = desk_card_html(leaky, TODAY)
    response = _redacted(leaky.model_dump(mode="json"))
    assert response["facts"]["reference"]["value"] == "BSN verborgen"
    assert hidden not in card
    assert hidden not in reminder_ics(leaky, uid="x@plainletter")

    # The control: an ordinary reference is not a citizen service number and stays readable, or
    # the visitor cannot pay.
    assert "8194 5523 7761" in desk_card_html(whole, TODAY)


def explanation_tags(card: str) -> set[str]:
    """The lang attributes on the explanation rows only."""
    return {
        match.group(1)
        for row in re.findall(r'<div class="prow">.*?</div>', card, re.S)
        for match in re.finditer(r'lang="([^"]+)"', row)
    }


def step_tags(card: str) -> set[str]:
    """The lang attributes on the action steps only."""
    return {
        match.group(1)
        for item in re.findall(r"<li>.*?</li>", card, re.S)
        for match in re.finditer(r'lang="([^"]+)"', item)
    }


def test_each_half_of_the_card_is_tagged_with_the_language_actually_printed_in_it() -> None:
    # Two languages can end up on the right-hand side of one card. A model asked for "nl, uk" can
    # answer "uk-UA", so the explanation rows fall back to the Dutch text while the planner, which
    # was handed the requested language, still wrote its steps in Ukrainian. Tagging both from
    # either one mislabels the other, and for a right-to-left language it also reverses it.
    whole = reading()
    dutch_only = whole.model_copy(
        update={"explanations": tuple(e for e in whole.explanations if e.language == "nl")}
    )
    card = desk_card_html(dutch_only, TODAY)
    assert explanation_tags(card) == {"nl"}, "the fallback rows are Dutch and must say so"
    assert step_tags(card) == {"uk"}, "the steps were written in the requested language"

    # The control: when the visitor's own explanation is there, both halves say the same thing.
    together = desk_card_html(whole, TODAY)
    assert explanation_tags(together) == {"uk"}
    assert step_tags(together) == {"uk"}
