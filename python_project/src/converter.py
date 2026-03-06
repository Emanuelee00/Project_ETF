"""Convert base Excel file to CSV containing ISIN column."""

import pandas as pd


def convert_excel_to_csv(input_file: str, output_file: str) -> None:
    """Convert Excel file to CSV."""
    df = pd.read_excel(input_file)
    df.to_csv(output_file, index=False, encoding="utf-8")


if __name__ == "__main__":
    convert_excel_to_csv(
        "../data/himalaya.xlsx",
        "../data/himalaya.csv"
    )
