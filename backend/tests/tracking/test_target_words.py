import pytest

from winnow.tracking.target_words import target_words


@pytest.mark.parametrize(
    ("instruction", "target"),
    [
        ("Put the marker in the pot", "pot"),
        ("Put one green sachet in the grey bowl.", "grey bowl"),
        ("Place the pack of doritos inside the sink", "sink"),
        ("Move the sharpie to the table", "table"),
        ("Take the pen out of the bowl and place it on the table", "table"),
        ("Put the candy bar on the left side of the first shelf", "first shelf"),
        ("Move the glass to the second row in the dishwasher", "dishwasher"),
        ("Put the white book on top of the tissue box.", "tissue box"),
        ("Put the towel on the bottle to the right", "bottle"),
        ("Move the pot to the top left corner of the table", "table"),
        ("Put the objects on the table into the cardboard box", "cardboard box"),
        ("Move the vaseline closer to the mirror", "mirror"),
        (
            "Pick up the black object from the striped towel and place it on the white sheet "
            "of paper on the right",
            "white sheet of paper",
        ),
    ],
)
def test_the_target_is_what_the_object_is_placed_in_or_on(instruction: str, target: str):
    assert target_words(instruction) == target


@pytest.mark.parametrize(
    "instruction",
    [
        "Move the black remote control to the left",  # a direction, not a place
        "Move the yellow mug forward",
        "Close the drawer",
        "",
    ],
)
def test_an_instruction_naming_no_place_has_no_target(instruction: str):
    assert target_words(instruction) is None
