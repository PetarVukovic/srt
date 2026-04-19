"""Local persistence for translation reports and per-request CSV summaries."""

from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LocalReportStore:
    """Store translation metadata and usage reports locally as CSV files."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def write_request_report(self, result: Dict[str, Any]) -> str:
        """Write a per-request CSV report and append to the global history CSV."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        base_name = result["base_name"]
        request_group = result.get("request_group") or "default"

        report_dir = Path(self.settings.reports_folder) / request_group
        report_dir.mkdir(parents=True, exist_ok=True)

        report_path = report_dir / f"{base_name}_{timestamp}.csv"
        rows = self._build_language_rows(result, timestamp)

        with report_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        self._append_global_history(rows)
        logger.info("Saved request CSV report: %s", report_path)
        return str(report_path)

    def _append_global_history(self, rows: List[Dict[str, Any]]) -> None:
        history_dir = Path(self.settings.reports_folder)
        history_dir.mkdir(parents=True, exist_ok=True)
        history_path = history_dir / "translation_history.csv"
        file_exists = history_path.exists()

        with history_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            if not file_exists:
                writer.writeheader()
            writer.writerows(rows)

    def _build_language_rows(self, result: Dict[str, Any], timestamp: str) -> List[Dict[str, Any]]:
        pricing = result.get("pricing", {})
        translated_files = result.get("translated_files", [])
        translated_lookup = {item["language"]: item for item in translated_files}
        complete_count = max(1, len(translated_files))

        input_cost = float(pricing.get("input_cost", 0.0))
        output_cost = float(pricing.get("output_cost", 0.0))
        total_cost = float(pricing.get("total_cost", 0.0))

        rows: List[Dict[str, Any]] = []
        for language in result.get("languages", []):
            translated_item = translated_lookup.get(language)
            validation = translated_item.get("validation", {}) if translated_item else {}
            rows.append(
                {
                    "timestamp_utc": timestamp,
                    "request_group": result.get("request_group") or "default",
                    "folder_id": result.get("folder_id") or "",
                    "base_name": result.get("base_name"),
                    "batch_name": result.get("batch_name"),
                    "model": pricing.get("model", ""),
                    "pricing_mode": pricing.get("pricing_mode", ""),
                    "language": language,
                    "status": "completed" if translated_item else "incomplete",
                    "coverage_percent": validation.get("coverage_percent", 0),
                    "missing_count": validation.get("missing_count", 0),
                    "output_file_path": translated_item.get("file_path", "") if translated_item else "",
                    "request_input_tokens": pricing.get("input_tokens", 0),
                    "request_output_tokens": pricing.get("output_tokens", 0),
                    "request_total_tokens": pricing.get("total_tokens", 0),
                    "request_input_cost_usd": round(input_cost, 6),
                    "request_output_cost_usd": round(output_cost, 6),
                    "request_total_cost_usd": round(total_cost, 6),
                    "estimated_input_cost_per_language_usd": round(input_cost / complete_count, 6),
                    "estimated_output_cost_per_language_usd": round(output_cost / complete_count, 6),
                    "estimated_total_cost_per_language_usd": round(total_cost / complete_count, 6),
                }
            )
        return rows
