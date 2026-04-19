"""SRT preprocessing utilities for cleaning and merging short subtitle segments."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from typing import List, Tuple

import chardet
import srt

TIME_PATTERN = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3}$")


def detect_file_encoding(file_path: str) -> str:
    """Detect file encoding with a conservative UTF-8 fallback."""
    try:
        with open(file_path, "rb") as f:
            raw_data = f.read(10000)
            result = chardet.detect(raw_data)
            encoding = result.get("encoding", "utf-8")
            confidence = result.get("confidence", 0)
            if confidence < 0.7:
                return "utf-8"
            return encoding
    except Exception:
        return "utf-8"


@dataclass
class MergeConfig:
    max_len_steps: Tuple[int, ...] = (60, 120, 140)
    min_duration: float = 1.0
    max_dist_forward: float = 0.1
    max_dist_backward: float = 1.0


class SRTMergePreprocessor:
    """Normalize malformed SRT files and merge short neighboring segments."""

    def __init__(self, config: MergeConfig | None = None):
        self.config = config or MergeConfig()

    def preprocess_file(self, input_path: str) -> dict:
        """Clean and merge a subtitle file in place."""
        encoding = detect_file_encoding(input_path)
        with open(input_path, "r", encoding=encoding) as f:
            original_content = f.read()

        normalized = original_content.replace("\r\n", "\n").replace("\r", "\n")
        fixed_content = self.fix_srt_timestamps(normalized)
        segments = self.parse_segments(fixed_content)
        merged_segments = self.merge_segments(segments)
        clean_segments, deleted_segments = self.validate_and_filter_segments(merged_segments)
        output_content = self.compose_segments(clean_segments)

        with open(input_path, "w", encoding="utf-8") as f:
            f.write(output_content)

        return {
            "original_segments": len(segments),
            "merged_segments": len(clean_segments),
            "deleted_segments": len(deleted_segments),
        }

    def fix_srt_timestamps(self, content: str) -> str:
        """Repair malformed timestamps and prevent overlaps."""

        def fix_time_format(value: str) -> str:
            if "," in value:
                base, ms = value.split(",", 1)
                return f"{base},{(ms + '000')[:3]}"
            return f"{value},000"

        lines = content.split("\n")
        raw_segments = []
        i = 0

        while i < len(lines):
            if lines[i].strip().isdigit():
                number = lines[i].strip()
                time_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
                text_lines = []
                j = i + 2
                while j < len(lines) and lines[j].strip():
                    text_lines.append(lines[j])
                    j += 1
                raw_segments.append({"num": number, "time": time_line, "text": text_lines})
                i = j
            else:
                i += 1

        pattern = re.compile(r"(\d{2}:\d{2}:\d{2},?\d*)\s*-->\s*(\d{2}:\d{2}:\d{2},?\d*)")

        for segment in raw_segments:
            match = pattern.match(segment["time"])
            if not match:
                continue
            start, end = match.groups()
            segment["time"] = f"{fix_time_format(start)} --> {fix_time_format(end)}"

        for idx, segment in enumerate(raw_segments):
            if " --> " not in segment["time"]:
                continue
            start, end = segment["time"].split(" --> ", 1)
            start_sec = self.to_seconds(start)
            end_sec = self.to_seconds(end)

            if idx > 0:
                prev_end = self.to_seconds(raw_segments[idx - 1]["time"].split(" --> ", 1)[1])
                start_sec = max(start_sec, prev_end)

            if idx < len(raw_segments) - 1 and " --> " in raw_segments[idx + 1]["time"]:
                next_start = self.to_seconds(raw_segments[idx + 1]["time"].split(" --> ", 1)[0])
                end_sec = min(end_sec, next_start)

            if end_sec <= start_sec:
                end_sec = start_sec + 0.001

            segment["time"] = f"{self.to_srt_time(start_sec)} --> {self.to_srt_time(end_sec)}"

        blocks = []
        for idx, segment in enumerate(raw_segments, start=1):
            text_block = "\n".join(segment["text"]).strip()
            blocks.append(f"{idx}\n{segment['time']}\n{text_block}".strip())

        return "\n\n".join(blocks).strip() + "\n"

    def parse_segments(self, content: str) -> List[dict]:
        """Parse SRT content into mutable segment dictionaries."""
        subtitles = list(srt.parse(content))
        return [
            {
                "num": idx,
                "start": self.to_srt_time(sub.start.total_seconds()),
                "end": self.to_srt_time(sub.end.total_seconds()),
                "text": sub.content.strip(),
                "orig_ids": [sub.index],
            }
            for idx, sub in enumerate(subtitles, start=1)
        ]

    def merge_segments(self, segments: List[dict]) -> List[dict]:
        """Merge short neighboring segments using a conservative heuristic."""
        current = [dict(seg) for seg in segments]
        for max_len in self.config.max_len_steps:
            current = self._merge_pass(current, max_len)
        for idx, seg in enumerate(current, start=1):
            seg["num"] = idx
        return current

    def _merge_pass(self, segments: List[dict], max_len: int) -> List[dict]:
        merged: List[dict] = []
        i = 0
        while i < len(segments):
            current = dict(segments[i])
            if i + 1 < len(segments):
                nxt = segments[i + 1]
                current_duration = self.to_seconds(current["end"]) - self.to_seconds(current["start"])
                next_duration = self.to_seconds(nxt["end"]) - self.to_seconds(nxt["start"])
                gap = self.to_seconds(nxt["start"]) - self.to_seconds(current["end"])

                can_merge = (
                    len(current["text"]) <= max_len
                    and len(nxt["text"]) <= max_len
                    and (current_duration < self.config.min_duration or next_duration < self.config.min_duration)
                    and gap <= self.config.max_dist_backward
                    and gap >= -self.config.max_dist_forward
                    and len(f"{current['text']} {nxt['text']}".strip()) <= max_len
                )
                if can_merge:
                    current["end"] = nxt["end"]
                    current["text"] = self._join_text(current["text"], nxt["text"])
                    current["orig_ids"] = sorted(set(current["orig_ids"] + nxt["orig_ids"]))
                    merged.append(current)
                    i += 2
                    continue

            merged.append(current)
            i += 1
        return merged

    def validate_and_filter_segments(self, segments: List[dict]) -> Tuple[List[dict], List[dict]]:
        """Drop invalid segments and renumber the remaining list."""
        valid_segments = []
        deleted_segments = []
        expected_number = 1

        for seg in segments:
            error_reason = None
            if seg["num"] != expected_number:
                error_reason = f"Wrong order (expected {expected_number})"
            elif not TIME_PATTERN.match(seg["start"]) or not TIME_PATTERN.match(seg["end"]):
                error_reason = "Invalid time format"
            elif seg["start"] >= seg["end"]:
                error_reason = "Start >= End"
            elif not seg["text"].strip():
                error_reason = "Empty text"

            if error_reason:
                deleted_segments.append(
                    {
                        "segment": seg["num"],
                        "time": f"{seg['start']} --> {seg['end']}",
                        "text": seg["text"],
                        "error": error_reason,
                    }
                )
            else:
                valid_segments.append(seg)
            expected_number += 1

        for idx, seg in enumerate(valid_segments, start=1):
            seg["num"] = idx

        return valid_segments, deleted_segments

    def compose_segments(self, segments: List[dict]) -> str:
        """Compose segment dictionaries back into SRT text."""
        subtitles = [
            srt.Subtitle(
                index=seg["num"],
                start=timedelta(seconds=self.to_seconds(seg["start"])),
                end=timedelta(seconds=self.to_seconds(seg["end"])),
                content=seg["text"],
            )
            for seg in segments
        ]
        return srt.compose(subtitles)

    @staticmethod
    def _join_text(left: str, right: str) -> str:
        if not left:
            return right
        if not right:
            return left
        return f"{left.rstrip()} {right.lstrip()}".strip()

    @staticmethod
    def to_seconds(value: str) -> float:
        hours, minutes, seconds_ms = value.split(":")
        seconds, millis = seconds_ms.split(",")
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000

    @staticmethod
    def to_srt_time(total_seconds: float) -> str:
        total_millis = max(0, round(total_seconds * 1000))
        hours, remainder = divmod(total_millis, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        seconds, millis = divmod(remainder, 1000)
        return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"
