from plainletter.text import canonical, fold_with_offsets, normalise, passage_is_in


def test_a_passage_is_found_across_line_breaks_and_soft_hyphens() -> None:
    letter = "Betaalt u niet op tijd,\ndan wordt het bedrag ver­hoogd met 50 procent."
    assert passage_is_in(
        letter, "Betaalt u niet op tijd, dan wordt het bedrag verhoogd met 50 procent."
    )


def test_a_passage_that_is_not_there_is_not_found() -> None:
    assert not passage_is_in("Betaal voor 15 september 2026.", "Betaal voor 1 oktober 2026.")


def test_the_fold_keeps_an_index_back_into_the_letter_for_every_character() -> None:
    # The mark is drawn on the original, so every folded character has to be able to say which
    # character of the letter it came from.
    folded, offsets = fold_with_offsets(canonical("Bedrag  EUR 174,00"))
    assert len(folded) == len(offsets)
    assert folded == "bedrag eur 174,00"
    assert offsets[folded.index("eur")] == "Bedrag  EUR 174,00".index("EUR")


def test_normalise_is_the_fold_with_the_map_thrown_away() -> None:
    text = "Kenmerk   8194­5523"
    assert normalise(text) == fold_with_offsets(canonical(text))[0]
