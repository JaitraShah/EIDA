import pandas as pd


def parse_csv(file_path: str) -> tuple[str, dict]:
    df = pd.read_csv(file_path)
    return df.to_string(index=False), {"rows": len(df), "columns": list(df.columns)}
