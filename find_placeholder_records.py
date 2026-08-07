"""
Run with:  python manage.py shell < find_placeholder_records.py

Finds Record rows whose technical-report fields contain the same
repeating placeholder string, and (optionally) clears them.
Dry-run by default -- set CLEAR = True to actually blank the fields.
"""

from apps.records.models import Record

CLEAR = False  # flip to True once you've reviewed the list below

FIELDS = ["case_description", "diagnosis", "repair_performed", "testing_results"]

def looks_like_placeholder(text: str) -> bool:
    """Heuristic: very long text made of a short repeating chunk."""
    text = (text or "").strip()
    if len(text) < 40:
        return False
    # Try chunk sizes from 5-30 chars and see if the string is
    # essentially that chunk repeated over and over.
    for chunk_len in range(5, 31):
        chunk = text[:chunk_len]
        if not chunk:
            continue
        repeated = (chunk * (len(text) // chunk_len + 1))[:len(text)]
        if repeated == text:
            return True
    return False

suspects = []
for record in Record.objects.all():
    hits = [f for f in FIELDS if looks_like_placeholder(getattr(record, f))]
    if hits:
        suspects.append((record, hits))

print(f"Found {len(suspects)} record(s) with placeholder-looking text:\n")
for record, hits in suspects:
    print(f"  Record #{record.id} - {record.title!r} - fields: {', '.join(hits)}")

if CLEAR:
    for record, hits in suspects:
        for field in hits:
            setattr(record, field, "")
        record.save(update_fields=hits)
    print(f"\nCleared {len(suspects)} record(s).")
else:
    print("\nDry run only -- set CLEAR = True at the top of this script to actually clear these fields.")
