"""Parse nginx access log lines and CSIC 2010 records into a common HTTPRequest shape."""
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import unquote, urlsplit


@dataclass
class HTTPRequest:
    method: str
    uri: str
    query: str
    body: str = ""
    headers: dict = field(default_factory=dict)


# nginx combined log format:
# $remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
_NGINX_RE = re.compile(
    r'^(?P<remote>\S+)\s+\S+\s+\S+\s+\[(?P<time>[^\]]+)\]\s+'
    r'"(?P<request>[^"]*)"\s+(?P<status>\d{3})\s+(?P<bytes>\S+)'
    r'(?:\s+"(?P<referer>[^"]*)"\s+"(?P<agent>[^"]*)")?'
)


def parse_nginx_line(line: str) -> Optional[HTTPRequest]:
    """Parse a single nginx access log line (Common or Combined format).

    Returns None if the line is malformed. Body is always empty (nginx access
    logs don't include request bodies by default).
    """
    line = line.strip()
    if not line:
        return None
    m = _NGINX_RE.match(line)
    if not m:
        return None
    request_line = m.group("request")
    parts = request_line.split(" ", 2)
    if len(parts) < 2:
        return None
    method = parts[0]
    raw_uri = parts[1]
    split = urlsplit(raw_uri)
    headers = {}
    if m.group("referer"):
        headers["Referer"] = m.group("referer")
    if m.group("agent"):
        headers["User-Agent"] = m.group("agent")
    return HTTPRequest(
        method=method,
        uri=split.path,
        query=split.query,
        body="",
        headers=headers,
    )


def parse_csic_record(block: str) -> Optional[HTTPRequest]:
    """Parse one HTTP request block from a CSIC 2010 text file.

    A block is a request-line, headers separated by '\\n', a blank line,
    and an optional body. CSIC publishes each block separated by blank
    lines from the next, but a block itself uses LF between header lines.
    """
    if not block or not block.strip():
        return None
    lines = block.splitlines()
    # First non-empty line is the request line
    idx = 0
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if idx >= len(lines):
        return None
    request_line = lines[idx]
    idx += 1
    parts = request_line.split(" ", 2)
    if len(parts) < 2:
        return None
    method = parts[0]
    raw_uri = parts[1]
    split = urlsplit(raw_uri)
    # Headers until blank line; body after
    headers = {}
    while idx < len(lines):
        line = lines[idx]
        idx += 1
        if not line.strip():
            break
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()
    body_lines = lines[idx:]
    body = "\n".join(body_lines).strip()
    # Some CSIC POSTs put the form-encoded body on a line; merge into query
    # for feature extraction purposes (the URL-anomaly features work on either).
    query = split.query
    if method.upper() == "POST" and body:
        if query:
            query = query + "&" + body
        else:
            query = body
    return HTTPRequest(
        method=method,
        uri=split.path,
        query=query,
        body=body,
        headers=headers,
    )


def split_csic_file(text: str) -> list[str]:
    """Split a CSIC file into per-request blocks.

    CSIC blocks end at a blank line. POST bodies don't contain blank lines
    in this dataset, so a single empty line is the safe delimiter.
    """
    blocks = []
    cur: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            if cur:
                blocks.append("\n".join(cur))
                cur = []
        else:
            cur.append(line)
    if cur:
        blocks.append("\n".join(cur))
    return blocks


def url_decode(s: str) -> str:
    """Best-effort URL decode that never raises."""
    try:
        return unquote(s)
    except Exception:
        return s
