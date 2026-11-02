"""The real transport: Meta's OpenAI-compatible Responses API, via the async OpenAI SDK, and
Voice Transcribe's batch endpoint, which the SDK doesn't cover."""

import json
from pathlib import Path
from typing import cast

import httpx2
import openai
from openai import AsyncOpenAI
from openai.types.responses import Response, ResponseInputParam

from standard_motion.meta.audio import transcript_from_response
from standard_motion.meta.models import MetaContent, Transcript
from standard_motion.meta.pricing import SAM
from standard_motion.meta.transport import FileGoneError, Reply, TransientError


def _as_input(content: MetaContent) -> ResponseInputParam:
    return cast(ResponseInputParam, [{"type": "message", "role": "user", "content": content}])


def _usage(response: Response) -> dict[str, int]:
    """Flatten usage, keeping SAM's extra `video_frames_processed` field."""
    if response.usage is None:
        return {}
    raw: dict[str, object] = response.usage.model_dump()
    usage = {k: int(v) for k, v in raw.items() if isinstance(v, int | float)}
    # SAM's usage may come without token details; the SDK doesn't validate responses.
    details = getattr(response.usage, "input_tokens_details", None)
    usage["cached_tokens"] = details.cached_tokens if details is not None else 0
    return usage


def _is_file_gone(error: openai.APIStatusError) -> bool:
    return error.status_code in (400, 404) and "file" in str(error.message).lower()


TRANSCRIBE_TIMEOUT_S = 60.0


class OpenAITransport:
    def __init__(self, base_url: str, api_key: str, http: httpx2.AsyncClient | None = None) -> None:
        # Retries are the client's job, so they share its backoff and budget handling.
        self._openai = AsyncOpenAI(base_url=base_url, api_key=api_key, max_retries=0)
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._http = http or httpx2.AsyncClient(timeout=TRANSCRIBE_TIMEOUT_S)

    async def upload(self, path: Path) -> str:
        with path.open("rb") as f:
            return (await self._openai.files.create(purpose="user_data", file=f)).id

    async def count_tokens(self, model: str, content: MetaContent) -> int:
        counted = await self._openai.responses.input_tokens.count(
            model=model, input=_as_input(content)
        )
        return counted.input_tokens

    async def respond(self, model: str, content: MetaContent, options: dict[str, object]) -> Reply:
        try:
            response = await self._send(model, content, options)
        except openai.APIConnectionError as e:
            raise TransientError(str(e)) from e
        except openai.APIStatusError as e:
            if e.status_code == 429 or e.status_code >= 500:
                raise TransientError(f"{e.status_code}: {e.message}") from e
            if _is_file_gone(e):
                raise FileGoneError(e.message) from e
            raise
        details = response.incomplete_details
        incomplete = (
            (details.reason or "unknown") if response.status == "incomplete" and details else None
        )
        return Reply(response.output_text, _usage(response), incomplete)

    async def _send(self, model: str, content: MetaContent, options: dict[str, object]) -> Response:
        # Options go in the body as-is: Meta's fields (SAM metadata) aren't in the SDK's types.
        if model == SAM:  # SAM answers long tracks as a stream
            async with self._openai.responses.stream(
                model=model, input=_as_input(content), extra_body=options
            ) as stream:
                return await stream.get_final_response()
        return await self._openai.responses.create(
            model=model, input=_as_input(content), extra_body=options
        )

    async def transcribe(self, model: str, audio: Path, options: dict[str, object]) -> Transcript:
        """Batch `POST /asr/transcribe`: a `request` JSON part and an `audio` part."""
        settings = json.dumps({"model": model, **options})
        files = {
            "request": (None, settings.encode(), "application/json"),
            "audio": (audio.name, audio.read_bytes(), "audio/wav"),
        }
        headers = {"Authorization": f"Bearer {self._api_key}", "Accept": "application/json"}
        try:
            response = await self._http.post(
                f"{self._base_url}/asr/transcribe", files=files, headers=headers
            )
        except httpx2.TransportError as e:
            raise TransientError(str(e)) from e
        if response.status_code == 429 or response.status_code >= 500:
            raise TransientError(f"{response.status_code}: {response.text[:200]}")
        if response.status_code >= 400:
            raise RuntimeError(f"Transcribe failed, {response.status_code}: {response.text[:200]}")
        return transcript_from_response(response.content)
