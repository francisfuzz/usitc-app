# Python API

Use `tariff_everywhere.py` when you want to query HTS data from your own Python code instead of going through the CLI or MCP server.

## Setup

### Local Python

```bash
git clone https://github.com/francisfuzz/tariff-everywhere.git
cd tariff-everywhere

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python scripts/ingest.py
```

The ingest step creates `data/hts.db`, which the API reads by default.

### Docker

```bash
docker build -t hts-local .
docker run --rm -v "$(pwd)/data:/app/data" hts-local scripts/ingest.py
```

To run Python code against the library in Docker:

```bash
docker run --rm \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd):/app" \
  -w /app \
  hts-local \
  -c "from tariff_everywhere import lookup_code; print(lookup_code('7408.11.30'))"
```

## Quick start

```python
from tariff_everywhere import get_chapters, list_chapter, lookup_code, search_hts

entry = lookup_code("7408.11.30")
print(entry["description"], entry["general_rate"])

matches = search_hts("copper wire", limit=20)
chapter_74 = list_chapter(74)
chapters = get_chapters()
```

## Database selection

By default, the library uses `data/hts.db`.

You can override that in either of these ways:

```python
from tariff_everywhere import lookup_code

entry = lookup_code("7408.11.30", db_path="/absolute/path/to/hts.db")
```

```bash
export HTS_DB_PATH=/absolute/path/to/hts.db
```

## Function reference

### `search_hts(keyword, limit=10, db_path=None) -> list[HTSEntry]`

Searches `hts_entries.description` with a SQL `LIKE` query.

```python
results = search_hts("copper wire", limit=5)
```

Returns an empty list when there are no matches.

### `lookup_code(code, db_path=None) -> HTSEntry | None`

Returns the first exact HTS code match.

```python
entry = lookup_code("7408.11.30")
if entry:
    print(entry["description"])
```

Returns `None` when the code is not present.

### `list_chapter(chapter_num, db_path=None) -> list[HTSEntry]`

Returns all entries in a chapter, ordered by HTS code. Single-digit chapters are zero-padded automatically.

```python
entries = list_chapter(7)
```

### `get_chapters(db_path=None) -> list[ChapterSummary]`

Returns chapter metadata with entry counts and freshness timestamps.

```python
for chapter in get_chapters():
    print(chapter["number"], chapter["description"], chapter["entry_count"])
```

## Return value structure

### `HTSEntry`

```json
{
  "id": 123,
  "hts_code": "7408.11.30",
  "indent": 3,
  "description": "Refined copper wire, of which the maximum cross-sectional dimension exceeds 9.5 mm",
  "unit": "kg",
  "general_rate": "3%",
  "special_rate": "Free (A,AU,BH,CL,CO,D,E,IL,JO,KR,MA,OM,P,PA,PE,S,SG)",
  "column2_rate": "8.5¢/kg",
  "chapter_id": 74
}
```

Schema notes:

- `general_rate`, `special_rate`, and `column2_rate` may be empty strings for structural entries.
- `indent` is the hierarchy depth in the HTS tree.
- `chapter_id` is the SQLite foreign key for the chapter row.

### `ChapterSummary`

```json
{
  "number": "74",
  "description": "Copper and Articles Thereof",
  "entry_count": 312,
  "last_checked_at": "2026-03-21T04:00:00+00:00",
  "last_changed_at": "2026-03-15T04:00:00+00:00"
}
```

## Error handling

### Missing database

If `data/hts.db` does not exist, the API raises `FileNotFoundError`.

```python
from tariff_everywhere import search_hts

try:
    search_hts("copper")
except FileNotFoundError:
    print("Run scripts/ingest.py first.")
```

### No results

- `search_hts(...)` returns `[]`
- `list_chapter(...)` returns `[]`
- `lookup_code(...)` returns `None`

These are normal result states, not exceptions.

## Common use cases

### Simple lookup

```python
from tariff_everywhere import lookup_code

entry = lookup_code("7408.11.30")
if entry:
    print(f"{entry['description']} - Duty: {entry['general_rate']}")
```

### Batch lookups from a list

```python
from tariff_everywhere import lookup_code

codes = ["0101.21.00", "0701.10.00", "7408.11.30"]
entries = [entry for code in codes if (entry := lookup_code(code))]
```

### Search by keyword

```python
from tariff_everywhere import search_hts

for item in search_hts("copper wire", limit=20):
    print(item["hts_code"], item["description"])
```

### Export to CSV

```python
import csv

from tariff_everywhere import search_hts

results = search_hts("copper wire", limit=20)

with open("tariffs.csv", "w", newline="") as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=["hts_code", "description", "general_rate", "special_rate", "column2_rate"],
    )
    writer.writeheader()
    writer.writerows(results)
```

### Export to JSON

```python
import json

from tariff_everywhere import get_chapters

with open("chapters.json", "w") as handle:
    json.dump(get_chapters(), handle, indent=2)
```

## Notes

- The Python API complements the CLI, MCP server, and Datasette interface; it does not replace them.
- The library is intended for local SQLite reads and low-concurrency workflows.
- Publishing to PyPI is a future enhancement; today the supported installation path is from this repository.
