"""Nepal SOS / mental health helplines shown on the SOS page.

!!! TODO (project team): every phone number and website below is a PLACEHOLDER. !!!
Verify each one with the organisation itself before any real use, then fill in
`phone` / `website` and set `verified=True`. Unverified entries are shown on the
SOS page as "number pending verification" so no unchecked number is ever displayed.
Organisation names are taken from the report's SOS screenshot and must be checked too.
"""

HOTLINES = [
    {
        "name": "National Mental Health Helpline",
        "phone": "TODO",
        "website": "",
        "hours": "",
        "verified": False,
    },
    {
        "name": "Samaritans Nepal",
        "phone": "TODO",
        "website": "",
        "hours": "",
        "verified": False,
    },
    {
        "name": "Mental Health Foundation Nepal",
        "phone": "TODO",
        "website": "",
        "hours": "",
        "verified": False,
    },
    {
        "name": "Nepal Counselling Line",
        "phone": "TODO",
        "website": "",
        "hours": "",
        "verified": False,
    },
    {
        "name": "MIASA Nepal",
        "phone": "TODO",
        "website": "",
        "hours": "",
        "verified": False,
    },
]

EMERGENCY = [
    {"name": "Police (emergency)", "phone": "TODO", "verified": False},
    {"name": "Ambulance", "phone": "TODO", "verified": False},
]


def display_phone(entry):
    """Number to show on the page; placeholders are never shown as if they were real."""
    if entry.get("verified") and entry.get("phone") and entry["phone"] != "TODO":
        return entry["phone"]
    return None
