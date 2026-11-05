"""Demo fixture: a tiny API serializer, broken by a schema change.

Original code assumed users carry 'username'. The new schema carries
'full_name'. The failing test (test_api.py) uses the new schema.
"""


def serialize_user(user):
    return {"id": user["id"], "name": user["username"]}
