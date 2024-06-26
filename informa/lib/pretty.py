import pandas as pd
from rich.console import Console
from rich.table import Table


def table(data: list[dict], columns: list[str], title: str | None = None):
    tbl = Table(title=title)

    for c in columns:
        tbl.add_column(c.title())

    for item in data:
        tbl.add_row(*[item[c] for c in columns])

    Console().print(tbl)


def dataframe(df: pd.DataFrame, title: str | None = None):
    tbl = Table(title=title)

    if 'date' in df.columns:
        df['date'] = df['date'].dt.strftime('%d-%m-%Y')

    for c in df.columns:
        tbl.add_column(c.title())

    for _, item in df.iterrows():
        tbl.add_row(*[str(s) for s in list(item)])

    Console().print(tbl)
