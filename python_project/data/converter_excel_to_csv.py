"""Convert base Excel file to clean CSV."""

import pandas as pd


def convert_excel_to_csv():
    """Convert himalaya.xlsx to cleaned himalaya.csv."""

    df = pd.read_excel("himalaya.xlsx")

    # Clean ISIN column
    df_clean = df.dropna(subset=["Code ISIN"])
    df_clean = df_clean[df_clean["Code ISIN"] != ""]

    df_clean.to_csv("himalaya.csv", index=False)

    print(df_clean["Code ISIN"])
    print("Columns:", df_clean.columns.tolist())

    print("Clean CSV created.")


if __name__ == "__main__":
    convert_excel_to_csv()
