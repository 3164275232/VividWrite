import argparse
import json
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path


def request(
    opener: urllib.request.OpenerDirector,
    url: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
) -> tuple[int, bytes]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    outgoing = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with opener.open(outgoing, timeout=20) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1")
    parser.add_argument("--password-file", required=True, type=Path)
    parser.add_argument("--username", default="tester01")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    password = args.password_file.read_text(encoding="utf-8").strip()
    public_opener = urllib.request.build_opener()

    home_status, home_body = request(public_opener, f"{base_url}/")
    assert home_status == 200 and b'id="root"' in home_body

    config_status, config_body = request(public_opener, f"{base_url}/api/auth/config")
    assert config_status == 200
    assert json.loads(config_body)["password_required"] is True

    protected_status, _ = request(
        public_opener,
        f"{base_url}/api/next-sentence",
        method="POST",
        payload={},
    )
    assert protected_status == 401

    authenticated_opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(CookieJar())
    )
    login_status, _ = request(
        authenticated_opener,
        f"{base_url}/api/auth/login",
        method="POST",
        payload={"username": args.username, "password": password},
    )
    assert login_status == 200

    me_status, me_body = request(authenticated_opener, f"{base_url}/api/auth/me")
    assert me_status == 200
    assert json.loads(me_body)["username"] == args.username

    logout_status, _ = request(
        authenticated_opener,
        f"{base_url}/api/auth/logout",
        method="POST",
        payload={},
    )
    assert logout_status == 200
    signed_out_status, _ = request(authenticated_opener, f"{base_url}/api/auth/me")
    assert signed_out_status == 401

    print(
        "auth_verification=passed "
        "home=200 unauthenticated_api=401 login=200 logout=200"
    )


if __name__ == "__main__":
    main()
