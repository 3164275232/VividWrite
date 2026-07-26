import argparse
import hashlib
import os
import re
import secrets
from pathlib import Path


PASSWORD_HASH_ITERATIONS = 310_000
MANAGED_KEYS = {
    "APP_AUTH_ENABLED",
    "APP_TEST_USERS",
    "APP_SHARED_PASSWORD_HASH",
    "APP_SESSION_SECRET",
    "APP_SESSION_TTL_SECONDS",
    "APP_COOKIE_SECURE",
}
USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,31}$")


def parse_existing_values(lines: list[str]) -> dict[str, str]:
    values = {}
    for line in lines:
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def create_password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    )
    return (
        f"pbkdf2_sha256:{PASSWORD_HASH_ITERATIONS}"
        f":{salt.hex()}:{digest.hex()}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True, type=Path)
    parser.add_argument("--password-file", required=True, type=Path)
    parser.add_argument("--users", required=True)
    args = parser.parse_args()

    users = [
        username.strip().lower()
        for username in args.users.split(",")
        if username.strip()
    ]
    if not users or any(not USERNAME_PATTERN.fullmatch(username) for username in users):
        raise SystemExit("Invalid test account list.")

    password = args.password_file.read_text(encoding="utf-8").strip()
    if len(password) < 12:
        raise SystemExit("The shared password must contain at least 12 characters.")

    original_lines = (
        args.env.read_text(encoding="utf-8").splitlines()
        if args.env.exists()
        else []
    )
    existing_values = parse_existing_values(original_lines)
    session_secret = existing_values.get("APP_SESSION_SECRET") or secrets.token_hex(32)

    retained_lines = [
        line
        for line in original_lines
        if line.split("=", 1)[0].strip() not in MANAGED_KEYS
    ]
    retained_lines.extend(
        [
            "",
            "# VividWrite research-test login",
            "APP_AUTH_ENABLED=true",
            f"APP_TEST_USERS={','.join(users)}",
            f"APP_SHARED_PASSWORD_HASH={create_password_hash(password)}",
            f"APP_SESSION_SECRET={session_secret}",
            "APP_SESSION_TTL_SECONDS=43200",
            "APP_COOKIE_SECURE=false",
        ]
    )

    temporary_path = args.env.with_suffix(f"{args.env.suffix}.tmp")
    temporary_path.write_text(
        "\n".join(retained_lines).rstrip() + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary_path, 0o600)
    temporary_path.replace(args.env)
    print(f"Configured {len(users)} test accounts: {', '.join(users)}")


if __name__ == "__main__":
    main()
