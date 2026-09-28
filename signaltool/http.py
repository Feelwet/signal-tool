"""Polite HTTP helper: per-host throttling, retries with backoff, optional disk cache."""
from __future__ import annotations
import hashlib, json, logging, time, threading
from urllib.parse import urlparse
import requests
from .config import USER_AGENT, RATE_LIMITS, DEFAULT_RATE, CACHE

log = logging.getLogger(__name__)
_last: dict[str, float] = {}
_lock = threading.Lock()
_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"})


def _throttle(host: str) -> None:
    gap = RATE_LIMITS.get(host, DEFAULT_RATE)
    with _lock:
        wait = _last.get(host, 0) + gap - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[host] = time.time()


def get(url: str, *, params=None, method="GET", json_body=None, retries=3, timeout=40,
        cache_hours: float | None = None, headers=None) -> requests.Response:
    """Fetch with throttling and retry on 429/5xx. Raises on final failure."""
    key = None
    if cache_hours:
        key = CACHE / ("http_" + hashlib.sha1(json.dumps([url, params, json_body], sort_keys=True, default=str).encode()).hexdigest())
        if key.exists() and time.time() - key.stat().st_mtime < cache_hours * 3600:
            r = requests.Response(); r.status_code = 200; r._content = key.read_bytes(); r.url = url
            return r
    host = urlparse(url).netloc
    delay = RATE_LIMITS.get(host, DEFAULT_RATE) * 2 + 2
    last_exc = None
    for attempt in range(retries):
        _throttle(host)
        try:
            r = _session.request(method, url, params=params, json=json_body, timeout=timeout, headers=headers)
            if r.status_code == 429 or r.status_code >= 500:
                last_exc = requests.HTTPError(f"{r.status_code} for {url}", response=r)
                log.info("retry %s after %s (%s)", url, delay, r.status_code)
                time.sleep(delay); delay *= 2
                continue
            r.raise_for_status()
            if key is not None:
                key.write_bytes(r.content)
            return r
        except requests.RequestException as e:
            last_exc = e
            if getattr(e, "response", None) is not None and e.response.status_code in (400, 401, 403, 404):
                break
            time.sleep(delay); delay *= 2
    raise last_exc  # type: ignore[misc]


def get_json(url, **kw):
    return get(url, **kw).json()


def retry_call(fn, *args, tries: int = 3, wait: float = 5.0, ok=None, what: str = "", **kw):
    """Call fn(*args, **kw) up to `tries` times with exponential backoff. A result for which ok(result) is False counts as a
    failure (e.g. an empty frame from a throttled Yahoo request); after the last try that result is returned as is.
    Exceptions are re-raised after the last try."""
    last_exc, res = None, None
    for i in range(tries):
        try:
            res = fn(*args, **kw)
            if ok is None or ok(res):
                return res
            last_exc = None
            log.info("retry %s: empty/invalid result (try %d/%d)", what or getattr(fn, "__name__", "call"), i + 1, tries)
        except Exception as e:     # network errors, JSON errors, Yahoo hiccups
            last_exc = e
            log.info("retry %s after error %s (try %d/%d)", what or getattr(fn, "__name__", "call"), e, i + 1, tries)
        if i < tries - 1:
            time.sleep(wait * (2 ** i))
    if last_exc is not None:
        raise last_exc
    return res


def yf_download(*args, **kw):
    """yfinance.download with retry (Yahoo drops requests or returns empty frames now and then)."""
    import yfinance as yf
    return retry_call(yf.download, *args, ok=lambda d: d is not None and len(d) > 0, what="yfinance", **kw)
