"""
Controlled, deterministic mutation set for CDC testing.
5 mutations cycling in order — covers UPDATE, INSERT, and DELETE.
After a full cycle the data is near-original state.
"""

MUTATIONS = [
    {
        "id": 1,
        "description": "Raise Beacon Corp credit limit (UPDATE accounts)",
        "table": "accounts",
        "operation": "UPDATE",
        "sql": 'UPDATE accounts SET credit_limit = %(credit_limit)s WHERE account_id = %(account_id)s',
        "params": {"credit_limit": 30000.00, "account_id": 2},
    },
    {
        "id": 2,
        "description": "Upgrade Carol from BRONZE to SILVER tier (UPDATE customers)",
        "table": "customers",
        "operation": "UPDATE",
        "sql": 'UPDATE customers SET tier = %(tier)s, active = %(active)s WHERE customer_id = %(customer_id)s',
        "params": {"tier": "SILVER", "active": True, "customer_id": 3},
    },
    {
        "id": 3,
        "description": "Enrol Dan in LOYALTY-BRONZE (INSERT memberships)",
        "table": "memberships",
        "operation": "INSERT",
        "sql": (
            "INSERT INTO memberships (membership_id, customer_id, program_code, points, enrolled_date, status) "
            "VALUES (%(membership_id)s, %(customer_id)s, %(program_code)s, %(points)s, %(enrolled_date)s, %(status)s) "
            "ON CONFLICT (membership_id) DO NOTHING"
        ),
        "params": {
            "membership_id": 99,
            "customer_id": 4,
            "program_code": "LOYALTY-BRONZE",
            "points": 10,
            "enrolled_date": "2025-01-01",
            "status": "ACTIVE",
        },
    },
    {
        "id": 4,
        "description": "Disable late payment fee rule (UPDATE rules)",
        "table": "rules",
        "operation": "UPDATE",
        "sql": 'UPDATE rules SET enabled = %(enabled)s WHERE rule_id = %(rule_id)s',
        "params": {"enabled": False, "rule_id": 1},
    },
    {
        "id": 5,
        "description": "Remove Dan's LOYALTY-BRONZE enrolment (DELETE memberships)",
        "table": "memberships",
        "operation": "DELETE",
        "sql": 'DELETE FROM memberships WHERE membership_id = %(membership_id)s',
        "params": {"membership_id": 99},
    },
]
