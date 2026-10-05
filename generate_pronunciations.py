import argparse
import base64
import csv
import hashlib
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_CSV = PROJECT_DIR / "Noongar categories.csv"
DEFAULT_OUTPUT = PROJECT_DIR / "web" / "audio"
MANIFEST_NAME = "manifest.json"
MODEL = "gemini-3.8-flash-tts"
VOICE = "Kore"
STYLE = (
    "Warm, natural, broad Australian English accent. Speak the supplied "
    "Noongar word exactly as written, slowly and clearly. Do not translate it "
    "or add any other words."
)
API_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"


def read_words(csv_path):
    with csv_path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            raise ValueError("The dictionary CSV has no header row.")
        headers = {
            (header or "").strip().casefold(): header
            for header in reader.fieldnames
        }
        noongar_header = headers.get("noongar")
        if noongar_header is None:
            raise ValueError("The dictionary CSV needs a 'Noongar' column.")
        return list(
            dict.fromkeys(
                word
                for row in reader
                if (word := (row.get(noongar_header) or "").strip())
            )
        )


def audio_filename(word):
    return f"{hashlib.sha256(word.encode('utf-8')).hexdigest()}.wav"


def read_manifest(path):
    if not path.exists():
        return {"model": MODEL, "voice": VOICE, "style": STYLE, "files": {}}
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read audio manifest {path}: {error}") from error
    if not isinstance(manifest, dict) or not isinstance(
        manifest.get("files"), dict
    ):
        raise ValueError(f"Audio manifest {path} has an invalid format.")
    return manifest


def write_manifest(path, manifest):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=".manifest-",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        json.dump(manifest, temporary, ensure_ascii=False, indent=2)
        temporary.write("\n")
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def request_audio(api_key, word, model, voice, style, timeout):
    payload = {
        "model": model,
        "input": [
            {
                "type": "user_input",
                "content": [
                    {
                        "type": "text",
                        "text": word,
                        "annotations": [
                            {"type": "speech_metadata", "style": style}
                        ],
                    }
                ],
            }
        ],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": voice}]},
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            if error.code == 429 or error.code >= 500:
                if attempt < 3:
                    print(
                        f"Google returned HTTP {error.code} for {word!r}; "
                        f"retrying ({attempt + 2}/4).",
                        flush=True,
                    )
                    time.sleep(2 ** attempt)
                    continue
            raise RuntimeError(
                f"Gemini API returned HTTP {error.code}: {details}"
            ) from error
        except (TimeoutError, urllib.error.URLError) as error:
            if attempt < 3:
                print(
                    f"Request for {word!r} failed ({error}); "
                    f"retrying ({attempt + 2}/4).",
                    flush=True,
                )
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Gemini API request failed: {error}") from error
    else:
        raise RuntimeError("Gemini API request failed after retries.")

    audio_blocks = [
        block
        for step in result.get("steps", [])
        if step.get("type") == "model_output"
        for block in step.get("content", [])
        if block.get("type") == "audio"
    ]
    if not audio_blocks or not audio_blocks[-1].get("data"):
        raise RuntimeError(f"Gemini returned no audio for {word!r}.")
    audio = base64.b64decode(audio_blocks[-1]["data"], validate=True)
    if not audio.startswith(b"RIFF") or audio[8:12] != b"WAVE":
        raise RuntimeError(f"Gemini returned an invalid WAV file for {word!r}.")
    return audio


def save_audio(path, audio):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=path.parent,
        prefix=".audio-",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        temporary.write(audio)
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate Noongar pronunciation WAVs using Google Gemini TTS."
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--voice", default=VOICE)
    parser.add_argument("--style", default=STYLE)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate existing files and replace the manifest.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the words that would be generated without calling Google.",
    )
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be a positive integer.")
    if args.delay < 0:
        parser.error("--delay cannot be negative.")
    if args.timeout <= 0:
        parser.error("--timeout must be positive.")
    return args


def main(argv=None):
    args = parse_args(argv)
    words = read_words(args.csv)
    manifest_path = args.output_dir / MANIFEST_NAME
    manifest = read_manifest(manifest_path)
    if manifest["files"] and not args.force and any(
        manifest.get(key) not in (None, value)
        for key, value in (
            ("model", args.model),
            ("voice", args.voice),
            ("style", args.style),
        )
    ):
        raise ValueError(
            "Existing audio was generated with different settings. "
            "Use --force to regenerate it."
        )
    files = {} if args.force else dict(manifest["files"])
    pending = [
        word
        for word in words
        if files.get(word) != audio_filename(word)
        or not (args.output_dir / audio_filename(word)).is_file()
    ]
    if args.limit is not None:
        pending = pending[:args.limit]
    if args.dry_run:
        print(f"{len(words)} distinct words; {len(pending)} audio files to generate.")
        for word in pending:
            print(word)
        return 0

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "Set GEMINI_API_KEY in your local environment before generating audio."
        )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "model": args.model,
        "voice": args.voice,
        "style": args.style,
        "files": files,
    }
    write_manifest(manifest_path, manifest)

    for index, word in enumerate(pending, start=1):
        print(f"[{index}/{len(pending)}] Requesting audio for {word}...", flush=True)
        audio = request_audio(
            api_key,
            word,
            args.model,
            args.voice,
            args.style,
            args.timeout,
        )
        filename = audio_filename(word)
        save_audio(args.output_dir / filename, audio)
        files[word] = filename
        write_manifest(manifest_path, manifest)
        print(f"[{index}/{len(pending)}] Generated {word}")
        if index < len(pending) and args.delay:
            time.sleep(args.delay)

    print(
        f"Audio ready for {len(files)} of {len(words)} distinct words "
        f"in {args.output_dir}."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Audio generation failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
