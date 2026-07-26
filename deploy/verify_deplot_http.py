import argparse
import json
import time
import urllib.request
import uuid
from pathlib import Path

from auth import AUTH_COOKIE_NAME, create_session_token


def create_multipart_body(image_path: Path, chart_type: str) -> tuple[bytes, str]:
    boundary = f"----VividWriteSmoke{uuid.uuid4().hex}"
    image_bytes = image_path.read_bytes()
    chunks = [
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="chart_type"\r\n\r\n',
        chart_type.encode(),
        b"\r\n",
        f"--{boundary}\r\n".encode(),
        (
            'Content-Disposition: form-data; name="image"; '
            f'filename="{image_path.name}"\r\n'
        ).encode(),
        b"Content-Type: image/png\r\n\r\n",
        image_bytes,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    return b"".join(chunks), boundary


def extract(
    url: str,
    image_path: Path,
    chart_type: str,
    session_token: str,
) -> tuple[dict, float]:
    body, boundary = create_multipart_body(image_path, chart_type)
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Cookie": f"{AUTH_COOKIE_NAME}={session_token}",
        },
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=600) as response:
        payload = json.loads(response.read())
        assert response.status == 200
    return payload, time.perf_counter() - started


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image_path", type=Path)
    parser.add_argument("--url", default="http://web/api/deplot-extract")
    parser.add_argument("--chart-type", default="bar")
    parser.add_argument("--username", default="tester01")
    args = parser.parse_args()

    session_token = create_session_token(args.username)
    first, first_seconds = extract(
        args.url,
        args.image_path,
        args.chart_type,
        session_token,
    )
    second, cached_seconds = extract(
        args.url,
        args.image_path,
        args.chart_type,
        session_token,
    )

    assert first["extracted_text"].strip()
    assert second["extracted_text"] == first["extracted_text"]
    assert cached_seconds < max(2.0, first_seconds / 10)

    print(
        "deplot_http_verification=passed "
        f"first_seconds={first_seconds:.2f} "
        f"cached_seconds={cached_seconds:.4f} "
        f"result_characters={len(first['extracted_text'])}"
    )


if __name__ == "__main__":
    main()
