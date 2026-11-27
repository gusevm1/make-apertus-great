import base64
import io
import wave

import httpx2

from tests.conftest import NO_TOOL_DECISION, FakeApertus

URL = "/api/transcriptions"


def make_wav(seconds: float, rate: int = 16000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(rate)
        recording.writeframes(b"\x00\x00" * round(seconds * rate))
    return buffer.getvalue()


async def test_transcription_sends_the_audio_to_the_smart_model(
    client: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    wav = make_wav(seconds=2)

    response = await client.post(URL, files={"file": ("voice.wav", wav, "audio/wav")})

    assert response.status_code == 200
    body = response.json()
    # The fake answers every call that sets a temperature with its tool decision.
    assert body["text"] == NO_TOOL_DECISION
    assert body["model"] == "fake-smart"
    assert isinstance(body["latency_ms"], int)
    [request] = apertus.requests
    assert request["model"] == "fake-smart"
    assert request["temperature"] == 0
    [message] = request["messages"]
    instruction, audio = message["content"]
    assert message["role"] == "user"
    assert "word for word" in instruction["text"]
    assert audio == {
        "type": "input_audio",
        "input_audio": {"data": base64.b64encode(wav).decode(), "format": "wav"},
    }


async def test_transcription_refuses_other_formats(
    client: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    response = await client.post(URL, files={"file": ("voice.mp3", b"ID3 not a wav", "audio/wav")})

    assert response.status_code == 415
    assert response.json()["error"] == "unsupported_media_type"
    assert "WAV" in response.json()["message"]
    assert apertus.requests == []


async def test_transcription_refuses_a_wav_without_a_frame_rate(
    client: httpx2.AsyncClient,
) -> None:
    wav = bytearray(make_wav(seconds=1))
    wav[24:28] = b"\x00\x00\x00\x00"

    response = await client.post(URL, files={"file": ("broken.wav", bytes(wav))})

    assert response.status_code == 415


async def test_transcription_refuses_long_and_large_recordings(
    client: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    too_long = make_wav(seconds=61, rate=8000)
    too_large = make_wav(seconds=59, rate=48000)

    long_response = await client.post(URL, files={"file": ("long.wav", too_long)})
    large_response = await client.post(URL, files={"file": ("large.wav", too_large)})

    assert long_response.status_code == 413
    assert "60 seconds" in long_response.json()["message"]
    assert large_response.status_code == 413
    assert "5 MB" in large_response.json()["message"]
    assert apertus.requests == []


async def test_recording_over_the_limit_is_refused_from_its_content_length(
    client: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    # The body is no valid form: only a refusal before reading it can answer 413.
    response = await client.post(
        URL,
        content=b"not read",
        headers={
            "content-type": "multipart/form-data; boundary=x",
            "content-length": str(6 * 1024 * 1024),
        },
    )

    assert response.status_code == 413
    assert response.json() == {
        "error": "payload_too_large",
        "message": "The recording is larger than 5 MB. Send a shorter one.",
    }
    assert apertus.requests == []
