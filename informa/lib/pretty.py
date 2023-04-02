from typing import List, Optional

from rich.console import Console
from rich.table import Table


def table(data: List[dict], columns: List[str], title: Optional[str]=None):
    tbl = Table(title=title)

    for c in columns:
        tbl.add_column(c.title())

    for item in data:
        row = []
        for c in columns:
            row.append(item[c])
        tbl.add_row(*row)

    Console().print(tbl)
