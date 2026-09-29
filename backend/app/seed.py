"""Demo unit records. Each one is chosen to exercise a scenario in the demo."""

from app import store
from app.core.models import ResidentType, UnitRecord

O, T = ResidentType.OWNER, ResidentType.TENANT

UNITS = {
    "green-valley": [
        UnitRecord(unit="A-101"),  # vacant: clean move-in
        UnitRecord(unit="A-102"),  # vacant
        UnitRecord(unit="A-201", occupant_name="Rahul Mehta", occupant_type=T),  # clean move-out
        UnitRecord(unit="A-202", occupant_name="Priya Nair", occupant_type=O, dues_outstanding=8200),  # dues block move-out
        UnitRecord(unit="B-301", occupant_name="Vikram Singh", occupant_type=T),  # occupied: move-in conflict
        UnitRecord(unit="B-302"),
    ],
    "sunrise-heights": [
        UnitRecord(unit="101"),
        UnitRecord(unit="102"),
        UnitRecord(unit="201", occupant_name="Neha Kapoor", occupant_type=T, dues_outstanding=3000),  # dues only warn here
        UnitRecord(unit="202", occupant_name="Arjun Das", occupant_type=O),
    ],
}


def seed_if_empty() -> None:
    if store.has_units():
        return
    for community_id, units in UNITS.items():
        for unit in units:
            store.save_unit(community_id, unit)
