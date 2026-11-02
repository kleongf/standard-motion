"""The words of the one Spark call that maps a turn's transcript onto unsure Phrases."""

VOICE_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["phrases"],
    "properties": {
        "phrases": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["phrase", "value", "quote"],
                "properties": {
                    "phrase": {"type": "string"},
                    "value": {"type": "string", "enum": ["pass", "fail"]},
                    "quote": {"type": "string"},
                },
            },
        }
    },
}


def voice_prompt(transcript: str, unsure: list[str]) -> str:
    phrases = "\n".join(f'- "{p}"' for p in unsure)
    return (
        "A reviewer is watching one recorded robot Episode and said this about it:\n\n"
        f'"{transcript}"\n\n'
        "These Phrases of the description of an expert Episode couldn't be decided "
        f"automatically:\n{phrases}\n\n"
        'For each Phrase the reviewer\'s words decide, answer "pass" if they say the Episode '
        'meets it and "fail" if they say it doesn\'t, quoting the few words that decide it. '
        "Give each Phrase's text exactly as listed. Leave out every Phrase they don't speak "
        "to; when they speak to none, answer an empty list."
    )
