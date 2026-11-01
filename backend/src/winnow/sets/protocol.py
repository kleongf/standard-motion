"""The evaluation protocol's rules for the two sets, checked before a freeze makes them permanent.

Nothing in the store says which Episodes were seen before the sets were defined: an Episode
records when it was ingested and when it joined a set, but not when the sets were "defined", and
the Test set's own Episodes are ingested just as early. So the seen Episodes are named here."""

from winnow.sets.models import SET_LABELS, EpisodeSet

TEST_SET_SIZE = 100

# Looked at by hand while the Rubric was being designed, so they can't be held out: the Dev set
# must hold them all, and the Test set none.
SEEN_EPISODES: tuple[str, ...] = (
    "droid_100:3",
    "droid_100:16",
    "droid_100:42",
    "droid_100:48",
    "droid_100:49",
    "droid_1.0.1:1",
    "droid_1.0.1:9",
    "droid_1.0.1:17",
)


def freeze_warnings(current: EpisodeSet) -> list[str]:
    """What freezing this set would break in the protocol; empty when it breaks nothing."""
    label = SET_LABELS[current.name]
    warnings: list[str] = []
    if current.name == "test":
        if current.size != TEST_SET_SIZE:
            warnings.append(
                f"The {label} should hold exactly {TEST_SET_SIZE} Episodes; it holds {current.size}"
            )
        seen = [i for i in SEEN_EPISODES if i in current.episode_ids]
        if seen:
            warnings.append(f"The {label} holds Episodes already seen: {', '.join(seen)}")
    if current.name == "dev":
        missing = [i for i in SEEN_EPISODES if i not in current.episode_ids]
        if missing:
            warnings.append(
                f"The {label} should hold every Episode already seen; missing {', '.join(missing)}"
            )
    return warnings
