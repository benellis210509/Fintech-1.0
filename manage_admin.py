"""Promote or demote an existing account from the server command line.

Examples:
    python3 manage_admin.py promote owner@example.com
    python3 manage_admin.py demote owner@example.com

Admin status is never granted from the public signup form or merely by knowing an
email address. Run this command only in a trusted shell connected to the correct
database.
"""

import argparse

from database import create_tables, get_connection


def set_admin(email, enabled):
    create_tables()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET is_admin = ? WHERE lower(email) = lower(?)",
            (1 if enabled else 0, email.strip()),
        )
        conn.commit()
        if cursor.rowcount != 1:
            raise SystemExit("No account was found for that email address.")
        status = "administrator" if enabled else "standard user"
        print("Updated {} to {}.".format(email.strip().lower(), status))
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Manage administrator access.")
    parser.add_argument("action", choices=("promote", "demote"))
    parser.add_argument("email")
    args = parser.parse_args()
    set_admin(args.email, args.action == "promote")


if __name__ == "__main__":
    main()
