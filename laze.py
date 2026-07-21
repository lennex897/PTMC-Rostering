
from roster_engine.personnel_repository import (
    load_personnel_from_supabase,
)

personnel = load_personnel_from_supabase()

print(f"Loaded {len(personnel)} active personnel")

for person in personnel[:10]:
    print(
        person.name,
        person.rank,
        person.centre,
        sorted(person.eligible_roles),
    )
