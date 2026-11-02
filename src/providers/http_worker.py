"""Private HTTP worker: isolated so DNS/connect/read all share a killable deadline."""
import json
import sys
import urllib.error
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    request = json.load(sys.stdin)
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + request["key"]}
    try:
        req = urllib.request.Request(request["url"], data=json.dumps(request["body"]).encode(), headers=headers)
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(req, timeout=request["timeout"]) as response:
            raw = response.read(request["max_bytes"] + 1)
            if len(raw) > request["max_bytes"]:
                result = {"error": "response_size_limit"}
            else:
                result = {"status": response.status, "body": json.loads(raw)}
    except urllib.error.HTTPError as exc:
        result = {"status": exc.code, "retry_after": exc.headers.get("Retry-After", "")}
    except (urllib.error.URLError, TimeoutError, OSError):
        result = {"error": "transport_error"}
    except (ValueError, KeyError):
        result = {"error": "provider_protocol"}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
