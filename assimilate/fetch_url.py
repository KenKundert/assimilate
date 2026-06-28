# DESCRIPTION {{{1
# Requests, but with error reporting

# IMPORTS {{{1
import requests
from requests.exceptions import (
    ConnectionError,
    Timeout,
    TooManyRedirects,
    HTTPError,
    SSLError,
    ProxyError,
    RequestException,
)
from inform import Error, full_stop


# fetch_url() {{{1
def fetch_url(url: str, method: str = "GET", **kwargs) -> requests.Response | None:
    """
    Wrapper around requests.get / requests.post with clean error reporting.

    Extra kwargs are forwarded to requests (json=, data=, headers=, timeout=, etc.)
    Returns the Response on success, None on failure.
    """
    method = method.upper()
    kwargs.setdefault("timeout", 10)

    try:
        response = requests.request(method, url, **kwargs)
        response.raise_for_status()  # turns 4xx/5xx into HTTPError
        return response
    except SSLError:
        raise Error("SSL certificate verification failed.", culprit=url)
    except ProxyError:
        raise Error("could not connect through configured proxy.")
    except ConnectionError:
        raise Error("connection error.", culprit=url)
    except Timeout:
        timeout_val = kwargs.get("timeout")
        raise Error(f"request timed out (> {timeout_val}s).", culprit=url)
    except TooManyRedirects:
        raise Error("too many redirects.", culprit=url)
    except HTTPError as e:
        status = e.response.status_code
        reason = e.response.reason
        messages = {
            400: "bad request — check the payload/params you sent.",
            401: "unauthorized — provide valid credentials.",
            403: "forbidden — you lack permission for this resource.",
            404: "not found — the URL may be wrong or the resource deleted.",
            408: "request timeout — the server gave up waiting.",
            429: "rate limited — slow down or back off.",
            500: "internal server error — the server is broken, not you.",
            502: "bad gateway — an upstream server returned an invalid response.",
            503: "service unavailable — the server is down or overloaded.",
            504: "gateway timeout — an upstream server timed out.",
        }
        message = messages.get(status, reason)
        raise Error(message, culprit=(url, f"error {status}"), response=response.text)
    except RequestException as e:
        # Catch-all for anything else in the requests exception hierarchy
        raise Error(f"unexpected error: {full_stop(e)}", culprit=url)
