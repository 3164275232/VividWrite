import argparse
import os
import secrets
from pathlib import Path


MANAGED_KEYS = {
    "APP_AUTH_ENABLED",
    "APP_TEST_USERS",
    "APP_RESEARCH_LOGGING_ENABLED",
    "APP_RESEARCH_CONSENT_REQUIRED",
    "APP_RESEARCH_CONSENT_VERSION",
    "APP_RESEARCH_ADMIN_KEY",
}


def parse_values(lines: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in lines:
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def participant_names(count: int) -> list[str]:
    if count < 1 or count > 99:
        raise ValueError("Participant count must be between 1 and 99.")
    return [f"tester{index:02d}" for index in range(1, count + 1)]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enable VividWrite research logging without changing the shared password."
    )
    parser.add_argument("--env", required=True, type=Path)
    parser.add_argument("--user-count", type=int, default=31)
    parser.add_argument("--consent-version", default="2026-09-01-v1")
    parser.add_argument("--admin-key-file", type=Path)
    args = parser.parse_args()

    original_lines = (
        args.env.read_text(encoding="utf-8").splitlines()
        if args.env.exists()
        else []
    )
    values = parse_values(original_lines)
    if not values.get("APP_SHARED_PASSWORD_HASH"):
        raise SystemExit(
            "APP_SHARED_PASSWORD_HASH is missing. Configure the shared login password first."
        )
    if not values.get("APP_SESSION_SECRET"):
        raise SystemExit("APP_SESSION_SECRET is missing. Configure authentication first.")

    users = participant_names(args.user_count)
    admin_key = values.get("APP_RESEARCH_ADMIN_KEY") or secrets.token_urlsafe(36)
    retained = [
        line
        for line in original_lines
        if line.split("=", 1)[0].strip() not in MANAGED_KEYS
    ]
    retained.extend(
        [
            "",
            "# VividWrite participant login and experiment data collection",
            "APP_AUTH_ENABLED=true",
            f"APP_TEST_USERS={','.join(users)}",
            "APP_RESEARCH_LOGGING_ENABLED=true",
            "APP_RESEARCH_CONSENT_REQUIRED=true",
            f"APP_RESEARCH_CONSENT_VERSION={args.consent_version}",
            f"APP_RESEARCH_ADMIN_KEY={admin_key}",
        ]
    )

    temporary = args.env.with_suffix(f"{args.env.suffix}.tmp")
    temporary.write_text("\n".join(retained).rstrip() + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(args.env)

    if args.admin_key_file:
        args.admin_key_file.parent.mkdir(parents=True, exist_ok=True)
        args.admin_key_file.write_text(admin_key + "\n", encoding="utf-8")
        os.chmod(args.admin_key_file, 0o600)

    print(f"Research logging enabled for {len(users)} accounts: {users[0]} to {users[-1]}.")
    if args.admin_key_file:
        print(f"Administrator key written to {args.admin_key_file} (value not displayed).")


if __name__ == "__main__":
    main()
