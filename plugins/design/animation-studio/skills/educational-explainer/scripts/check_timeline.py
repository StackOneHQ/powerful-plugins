#!/usr/bin/env python3
"""Check declared scene/caption timing against local PCM WAV durations."""

from __future__ import annotations

import argparse
import json
import math
import sys
import wave
from pathlib import Path
from typing import Any


def integer(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def check(plan: dict[str, Any], root: Path) -> list[str]:
    fps = integer(plan.get("fps"), "fps", 1)
    total = integer(plan.get("total_frames"), "total_frames", 1)
    scenes = plan.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("scenes must be a nonempty list")
    errors: list[str] = []
    previous_end = 0
    ids: set[str] = set()
    for scene in scenes:
        if not isinstance(scene, dict):
            raise ValueError("each scene must be an object")
        scene_id = scene.get("id")
        if not isinstance(scene_id, str) or not scene_id or scene_id in ids:
            raise ValueError("scene ids must be nonempty and unique")
        ids.add(scene_id)
        start = integer(scene.get("start_frame"), f"{scene_id}.start_frame")
        end = integer(scene.get("end_frame"), f"{scene_id}.end_frame", 1)
        if start != previous_end or end <= start or end > total:
            errors.append(f"{scene_id}: scenes must be contiguous and inside total_frames")
        previous_end = end
        transcript = scene.get("transcript")
        captions = scene.get("captions")
        if not isinstance(transcript, str) or not isinstance(captions, list):
            raise ValueError(f"{scene_id}: transcript and captions are required")
        audio = scene.get("audio")
        if audio is None:
            if transcript.strip() or captions:
                errors.append(f"{scene_id}: silent scene has narration or captions")
            continue
        if not isinstance(audio, str) or not audio:
            raise ValueError(f"{scene_id}: audio must be a relative WAV path or null")
        audio_path = (root / audio).resolve()
        if Path(audio).is_absolute() or not audio_path.is_relative_to(root.resolve()):
            raise ValueError(f"{scene_id}: audio must stay inside the plan directory")
        with wave.open(str(audio_path), "rb") as handle:
            samples, rate = handle.getnframes(), handle.getframerate()
            # Detect a truncated WAV rather than trusting its declared frame count.
            raw = handle.readframes(samples)
            if len(raw) != samples * handle.getsampwidth() * handle.getnchannels():
                raise ValueError(f"{scene_id}: truncated WAV")
        if samples == 0:
            errors.append(f"{scene_id}: empty narration audio")
        if math.ceil(samples * fps / rate) > end - start:
            errors.append(f"{scene_id}: narration exceeds scene duration")
        if not transcript.strip() or not captions:
            errors.append(f"{scene_id}: narrated scene needs transcript and captions")
        caption_end = start
        words = []
        for caption in captions:
            if not isinstance(caption, dict) or not isinstance(caption.get("text"), str):
                raise ValueError(f"{scene_id}: invalid caption")
            cstart = integer(caption.get("start_frame"), "caption.start_frame")
            cend = integer(caption.get("end_frame"), "caption.end_frame", 1)
            if cstart < caption_end or cend <= cstart or cend > end or cstart < start:
                errors.append(f"{scene_id}: caption overlaps or lies outside its scene")
            if not caption["text"].strip():
                errors.append(f"{scene_id}: empty caption")
            caption_end = cend
            words.extend(caption["text"].split())
        if words != transcript.split():
            errors.append(f"{scene_id}: captions differ from transcript")
    if previous_end != total:
        errors.append("final scene does not end at total_frames")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    args = parser.parse_args()
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        if not isinstance(plan, dict):
            raise ValueError("plan must be an object")
        errors = check(plan, args.plan.parent)
    except (OSError, ValueError, wave.Error, EOFError) as error:
        print(f"timeline: could not check: {error}", file=sys.stderr)
        return 2
    for finding in errors:
        print(f"timeline: {finding}")
    if not errors:
        print("Timeline and WAV durations are consistent. Inspect the final render separately.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
