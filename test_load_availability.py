from roster_engine.database import get_supabase
from roster_engine.availability_repository import AvailabilityRepository

repo = AvailabilityRepository(get_supabase())

entries = repo.load_month_availability(
    year=2026,
    month=8,
)

print(f"Loaded {len(entries)} availability entries")

for entry in entries[:10]:
    print(
        entry.person_name,
        entry.unavailable_date,
        entry.reason,
    )