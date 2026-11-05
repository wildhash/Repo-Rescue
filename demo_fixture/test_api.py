"""Independent verifier test for the demo fixture (stdlib only)."""

from api import serialize_user


def test_serialize_user_new_schema():
    user = {"id": 42, "full_name": "Ada"}
    assert serialize_user(user) == {"id": 42, "name": "Ada"}


if __name__ == "__main__":
    test_serialize_user_new_schema()
    print("PASS")
