"""
power_outage_analysis.py
=========================

Object-oriented pipeline for analysing India's power outage data
(Ministry of Power, 2017-2024).

The PowerOutageAnalysis class implements the six-stage pipeline:
    1. load_data()        -> read the raw CSV
    2. clean_data()        -> handle missing values, duplicates, dtypes
    3. calculate_downtime()-> derive a Downtime_Days column
    4. analyze_data()      -> state / sector / trend / downtime analysis
    5. visualize()          -> bar / line / pie charts saved to disk
    6. generate_report()   -> plain-text summary of insights

Usage
-----
    from src.power_outage_analysis import PowerOutageAnalysis

    poa = PowerOutageAnalysis()
    poa.load_data("data/Daily Power Outage_Sample_Data.csv")
    poa.clean_data()
    poa.calculate_downtime()
    poa.analyze_data()
    poa.visualize(output_dir="outputs")
    poa.generate_report("outputs/report.txt")
"""

from __future__ import annotations

import os
from typing import Optional

import pandas as pd
import matplotlib.pyplot as plt


class PowerOutageAnalysis:
    """Encapsulates the full outage-analysis pipeline as reusable, testable steps."""

    # Column names as they appear in the Ministry of Power sample export.
    COL_OUTAGE_DATE = "Outage Date (outage_date)"
    COL_SYNC_DATE = "Expected or Synchronize Date (expected_sync_date)"
    COL_REMARKS = "Remarks (remarks)"
    COL_SECTOR = "Sector (sector)"

    def __init__(self) -> None:
        self.data: Optional[pd.DataFrame] = None
        self.cleaned_data: Optional[pd.DataFrame] = None
        self._results: dict = {}

    # ------------------------------------------------------------------ #
    # 1. Load
    # ------------------------------------------------------------------ #
    def load_data(self, file_path: str) -> pd.DataFrame:
        """Read the raw CSV export into memory."""
        self.data = pd.read_csv(file_path)
        print(f"Loaded {len(self.data):,} rows from '{file_path}'.")
        return self.data

    # ------------------------------------------------------------------ #
    # 2. Clean
    # ------------------------------------------------------------------ #
    def clean_data(self) -> pd.DataFrame:
        """Parse dates, drop unusable rows, and normalise text fields."""
        if self.data is None:
            raise RuntimeError("Call load_data() before clean_data().")

        df = self.data.copy()

        # Parse the two date columns; unparsable values become NaT.
        df[self.COL_OUTAGE_DATE] = pd.to_datetime(df[self.COL_OUTAGE_DATE], errors="coerce")
        df[self.COL_SYNC_DATE] = pd.to_datetime(df[self.COL_SYNC_DATE], errors="coerce")

        # Rows without both dates can't be used for downtime calculations.
        df = df.dropna(subset=[self.COL_OUTAGE_DATE, self.COL_SYNC_DATE])

        # Remove exact duplicate records.
        df = df.drop_duplicates()

        self.cleaned_data = df
        print(f"Cleaned dataset: {len(df):,} rows remain.")
        return df

    # ------------------------------------------------------------------ #
    # 3. Downtime
    # ------------------------------------------------------------------ #
    def calculate_downtime(self) -> pd.DataFrame:
        """Add a Downtime_Days column and drop implausible (negative) values."""
        if self.cleaned_data is None:
            raise RuntimeError("Call clean_data() before calculate_downtime().")

        df = self.cleaned_data
        df["Downtime_Days"] = (
            df[self.COL_SYNC_DATE] - df[self.COL_OUTAGE_DATE]
        ).dt.days
        df = df[df["Downtime_Days"] >= 0]

        df["Year"] = df[self.COL_OUTAGE_DATE].dt.year
        df["Month"] = df[self.COL_OUTAGE_DATE].dt.month

        self.cleaned_data = df
        print(f"Downtime calculated for {len(df):,} valid records.")
        return df

    # ------------------------------------------------------------------ #
    # 4. Analyze
    # ------------------------------------------------------------------ #
    def analyze_data(self) -> dict:
        """Run the statistical aggregations used throughout the report."""
        if self.cleaned_data is None:
            raise RuntimeError("Call calculate_downtime() before analyze_data().")

        df = self.cleaned_data

        top_reasons = df[self.COL_REMARKS].fillna("Unknown").value_counts().head(10)

        sector_analysis = df.groupby(self.COL_SECTOR)["Downtime_Days"].agg(
            Total_Outages="count",
            Average_Downtime="mean",
            Maximum_Downtime="max",
        )

        yearly_outages = df.groupby("Year").size()

        self._results = {
            "top_reasons": top_reasons,
            "sector_analysis": sector_analysis,
            "yearly_outages": yearly_outages,
        }
        return self._results

    # ------------------------------------------------------------------ #
    # 5. Visualize
    # ------------------------------------------------------------------ #
    def visualize(self, output_dir: str = "outputs") -> None:
        """Save the standard chart set (bar + line) as PNG files."""
        if not self._results:
            raise RuntimeError("Call analyze_data() before visualize().")

        os.makedirs(output_dir, exist_ok=True)

        # Top outage reasons (bar chart)
        plt.figure(figsize=(10, 5))
        self._results["top_reasons"].plot(kind="bar")
        plt.title("Top 10 Reasons for Power Plant Outages")
        plt.xlabel("Reason")
        plt.ylabel("Count")
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "top_outage_reasons.png"))
        plt.close()

        # Year-wise outages (line chart)
        plt.figure(figsize=(8, 5))
        self._results["yearly_outages"].plot(marker="o")
        plt.title("Year-wise Power Plant Outages")
        plt.xlabel("Year")
        plt.ylabel("Number of Outages")
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "yearly_outages.png"))
        plt.close()

        print(f"Charts saved to '{output_dir}/'.")

    # ------------------------------------------------------------------ #
    # 6. Report
    # ------------------------------------------------------------------ #
    def generate_report(self, output_path: str = "outputs/report.txt") -> str:
        """Write a plain-text summary of the key findings."""
        if not self._results:
            raise RuntimeError("Call analyze_data() before generate_report().")

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        lines = [
            "NATIONAL POWER OUTAGE ANALYSIS - SUMMARY REPORT",
            "=" * 50,
            "",
            f"Total cleaned records analysed: {len(self.cleaned_data):,}",
            "",
            "Top 10 Outage Reasons:",
            self._results["top_reasons"].to_string(),
            "",
            "Sector Reliability (downtime in days):",
            self._results["sector_analysis"].to_string(),
            "",
            "Year-wise Outage Counts:",
            self._results["yearly_outages"].to_string(),
            "",
        ]

        report_text = "\n".join(lines)
        with open(output_path, "w") as f:
            f.write(report_text)

        print(f"Report written to '{output_path}'.")
        return report_text

    # ------------------------------------------------------------------ #
    # Convenience
    # ------------------------------------------------------------------ #
    def export_cleaned_data(self, output_path: str = "outputs/cleaned_power_outages.csv") -> None:
        """Persist the cleaned dataframe for downstream use."""
        if self.cleaned_data is None:
            raise RuntimeError("No cleaned data to export.")
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        self.cleaned_data.to_csv(output_path, index=False)
        print(f"Cleaned data exported to '{output_path}'.")


if __name__ == "__main__":
    poa = PowerOutageAnalysis()
    poa.load_data("data/Daily Power Outage_Sample_Data.csv")
    poa.clean_data()
    poa.calculate_downtime()
    poa.analyze_data()
    poa.visualize(output_dir="outputs")
    poa.generate_report("outputs/report.txt")
    poa.export_cleaned_data("outputs/cleaned_power_outages.csv")
    print("\nAnalysis completed successfully!")
