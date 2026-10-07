#!/usr/bin/env bash
# HTTP smoke test for a running Racheeta backend in PRODUCTION mode behind a TLS-terminating
# proxy (SECURE_PROXY_SSL=true, TRUSTED_PROXY_COUNT=1). It changes nothing on the server.
#
#   scripts/smoke_http.sh http://127.0.0.1:8000 [expected-host]
#
# Needs only curl. Exits non-zero on the first failed expectation. Used by CI
# (scripts/container_smoke.sh) and by operators after a staging/production deploy.
set -u

BASE="${1:?usage: smoke_http.sh BASE_URL [HOST_HEADER]}"
HOST_HDR="${2:-}"
fail=0
host_args=()
[ -n "$HOST_HDR" ] && host_args=(-H "Host: $HOST_HDR")

ok()   { printf '  ok    %s\n' "$1"; }
bad()  { printf '  FAIL  %s\n' "$1"; fail=1; }

status() { curl -s -o /dev/null -w '%{http_code}' ${host_args[@]+"${host_args[@]}"} "$@"; }
headers() { curl -s -o /dev/null -D - ${host_args[@]+"${host_args[@]}"} "$@" | tr -d '\r'; }

expect_status() { # description expected curl-args...
  local desc="$1" want="$2"; shift 2
  local got; got="$(status "$@")"
  if [ "$got" = "$want" ]; then ok "$desc ($got)"; else bad "$desc: expected $want, got $got"; fi
}

echo "Racheeta HTTP smoke against $BASE"
[ "$(status "$BASE/health/")" != "000" ] || { echo "cannot connect to $BASE"; exit 2; }

# Liveness / readiness are reachable over plain HTTP (the platform health check cannot send
# X-Forwarded-Proto), and must not redirect.
expect_status "/health/ is 200 over plain HTTP" 200 "$BASE/health/"
expect_status "/ready/ is 200 (database reachable)" 200 "$BASE/ready/"
ready_body="$(curl -s ${host_args[@]+"${host_args[@]}"} "$BASE/ready/")"
case "$ready_body" in *'"ready"'*) ok "/ready/ body reports ready";; *) bad "/ready/ body: $ready_body";; esac

# Everything else is forced to HTTPS...
loc="$(headers "$BASE/api/v1/geo/governorates" | awk 'tolower($1)=="location:"{print $2}')"
case "$loc" in https://*) ok "plain-HTTP API request redirects to HTTPS";; *) bad "no HTTPS redirect (Location: '$loc')";; esac

# ...and served with the proxy's forwarded-proto header present.
SECURE=(-H "X-Forwarded-Proto: https")
expect_status "public API answers over (proxied) HTTPS" 200 "${SECURE[@]}" "$BASE/api/v1/geo/governorates"
expect_status "protected API rejects anonymous callers" 401 "${SECURE[@]}" "$BASE/api/v1/me"
expect_status "API docs are not exposed by default" 404 "${SECURE[@]}" "$BASE/api/docs/"
expect_status "OpenAPI schema is not exposed by default" 404 "${SECURE[@]}" "$BASE/api/schema/"

h="$(headers "${SECURE[@]}" "$BASE/api/v1/geo/governorates")"
need() { # header-name-regex description
  if printf '%s\n' "$h" | grep -qiE "$1"; then ok "$2"; else bad "$2 (missing)"; fi
}
need '^content-security-policy:.*default-src' "Content-Security-Policy present"
need '^x-content-type-options: *nosniff' "X-Content-Type-Options: nosniff"
need '^referrer-policy: *no-referrer' "Referrer-Policy: no-referrer"
need '^strict-transport-security:' "HSTS present"
need '^x-frame-options: *deny' "X-Frame-Options: DENY"
need '^permissions-policy:' "Permissions-Policy present"
need '^x-request-id:' "X-Request-ID returned"
if printf '%s\n' "$h" | grep -qiE "^content-security-policy:.*unsafe-eval"; then
  bad "CSP contains unsafe-eval"; else ok "CSP has no unsafe-eval"; fi

# A client-supplied request id is echoed only if well formed; garbage is replaced.
echoed="$(headers "${SECURE[@]}" -H 'X-Request-ID: smoke-test-0001' "$BASE/health/" \
  | awk 'tolower($1)=="x-request-id:"{print $2}')"
[ "$echoed" = "smoke-test-0001" ] && ok "valid X-Request-ID is propagated" \
  || bad "valid X-Request-ID not propagated ('$echoed')"
evil="$(headers "${SECURE[@]}" -H 'X-Request-ID: bad id with spaces' "$BASE/health/" \
  | awk 'tolower($1)=="x-request-id:"{print $2}')"
[ -n "$evil" ] && [ "$evil" != "bad" ] && ok "malformed X-Request-ID is replaced" \
  || bad "malformed X-Request-ID mishandled ('$evil')"

# No stack traces / debug pages on an error.
body="$(curl -s ${host_args[@]+"${host_args[@]}"} "${SECURE[@]}" "$BASE/api/v1/does-not-exist")"
[ -n "$body" ] || bad "404 probe returned no body"
if printf '%s' "$body" | grep -qiE "traceback|django|settings"; then
  bad "error response leaks internals"; else ok "404 response leaks nothing"; fi

if [ "$fail" -ne 0 ]; then echo "SMOKE FAILED"; exit 1; fi
echo "SMOKE PASSED"
