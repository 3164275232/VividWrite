import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path


def read_admin_key(args: argparse.Namespace) -> str:
    if args.admin_key:
        return args.admin_key.strip()
    if args.admin_key_file:
        return args.admin_key_file.read_text(encoding="utf-8").strip()
    raise SystemExit("Provide --admin-key-file (recommended) or --admin-key.")


def request_data(base_url: str, path: str, admin_key: str) -> tuple[bytes, str]:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        headers={"X-Research-Admin-Key": admin_key},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.read(), response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Server returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Could not connect to {base_url}: {exc.reason}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="View or download VividWrite study data.")
    parser.add_argument("--base-url", required=True, help="For example: http://server-ip")
    parser.add_argument("--admin-key-file", type=Path)
    parser.add_argument("--admin-key")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--list", action="store_true", help="List participant data counts.")
    action.add_argument("--participant", help="Download one account, for example tester07.")
    action.add_argument("--all", action="store_true", help="Download all participant data.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    key = read_admin_key(args)

    if args.list:
        body, _ = request_data(args.base_url, "/api/research/admin/participants", key)
        data = json.loads(body)
        print("account    sessions  events  artifacts  last activity")
        for item in data.get("participants", []):
            print(
                f"{item['username']:<10} {item['session_count']:>8} "
                f"{item['event_count']:>7} {item['artifact_count']:>10}  "
                f"{item.get('last_seen_at') or '-'}"
            )
        return

    if args.participant:
        username = args.participant.strip().lower()
        if not username.startswith("tester"):
            raise SystemExit("Participant must be a tester account name.")
        path = f"/api/research/admin/export/{username}"
        output = args.output or Path(f"vividwrite-{username}-research-data.zip")
    else:
        path = "/api/research/admin/export-all"
        output = args.output or Path("vividwrite-all-participants-research-data.zip")

    body, content_type = request_data(args.base_url, path, key)
    if "zip" not in content_type.lower():
        raise SystemExit(f"Expected a ZIP response, received {content_type or 'unknown content type'}.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(body)
    print(f"Downloaded {len(body):,} bytes to {output.resolve()}")


if __name__ == "__main__":
    main()
