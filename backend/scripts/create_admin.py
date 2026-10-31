# -----------------------------------------------------------------------------
# backend/scripts/create_admin.py
#
# Creates an admin user. Public registration only creates partners, so this
# is the only way to bootstrap an admin account.
#
# Usage (from backend/, or inside the backend container):
#   python -m scripts.create_admin --email admin@referrai.dev --password 'S3cure-pass'
#   docker compose exec backend python -m scripts.create_admin --email ... --password ...
#
# Exits 0 if the admin was created or already exists (idempotent for seeding).
# -----------------------------------------------------------------------------

import argparse
import asyncio
import sys

from app.core.database import AsyncSessionLocal, engine
from app.services.auth_service import AuthService, EmailAlreadyRegisteredError


async def _main(email: str, password: str) -> int:
    if len(password) < 8:
        print("Password must be at least 8 characters", file=sys.stderr)
        return 2
    try:
        async with AsyncSessionLocal() as session:
            user = await AuthService(session).create_admin(email, password)
        print(f"Created admin {user.email} ({user.id})")
    except EmailAlreadyRegisteredError:
        print(f"User {email} already exists — nothing to do")
    finally:
        await engine.dispose()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a ReferrAI admin user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    sys.exit(asyncio.run(_main(args.email, args.password)))


if __name__ == "__main__":
    main()
