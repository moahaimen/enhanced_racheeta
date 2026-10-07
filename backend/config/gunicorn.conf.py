"""Gunicorn settings for the single-service Railway deployment (`scripts/start.sh -c`).

Sized for the smallest plan: a few sync workers, no threads, no async worker class. Everything is
overridable by the environment variables named below; nothing here is a secret.
"""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# Two sync workers fit a small instance; raise WEB_CONCURRENCY only with measured CPU/RAM headroom.
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
# A request (including a synchronous SMTP send, bounded by EMAIL_TIMEOUT) must finish well
# inside this.
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "60"))
# On SIGTERM (Railway redeploy) let in-flight requests finish before the worker is killed.
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", "30"))
# The platform proxy reuses connections; a short keep-alive frees workers promptly.
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", "5"))
# Recycle workers periodically to bound slow memory growth; jitter avoids a simultaneous restart.
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", "2000"))
max_requests_jitter = int(os.environ.get("GUNICORN_MAX_REQUESTS_JITTER", "200"))
# Heartbeat files in RAM: the default (/tmp on disk) can stall workers on slow container disks.
# (Linux containers only; absent on a developer's macOS, where gunicorn then uses its default.)
_SHM = "/dev/shm"  # noqa: S108 - RAM-backed heartbeat dir, not a temp-file race
worker_tmp_dir = _SHM if os.path.isdir(_SHM) else None

# Logs go to stdout/stderr (Railway collects them).
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
# Privacy: the e-mail links (/reset-password?uid=…&token=…, /verify-email?…) carry one-time
# tokens in the QUERY STRING, and the Referer of later requests can carry them too. The
# default access-log format records both (`%(r)s` the request line, `%(f)s` the referer), so
# this format logs the path only (`%(U)s`, no query), no referer and no client-controlled
# headers.
access_log_format = '%(h)s "%(m)s %(U)s" %(s)s %(b)s %(L)ss'
