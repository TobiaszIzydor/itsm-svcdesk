# ai-generated: 80% - Claude Code wrote the test cases for semgrep/rules.yml from my two decisions about svcdesk
import json
import urllib.request

from fastapi import APIRouter

router = APIRouter()


@router.get("/kb/search")
def kb_search(q: str):
    # ruleid: svcdesk-upstream-call-in-handler
    with urllib.request.urlopen("http://kb-index:8080/search?q=" + q, timeout=5) as upstream:
        return json.loads(upstream.read())


@router.get("/kb/async")
async def kb_async(q: str):
    # ruleid: svcdesk-upstream-call-in-handler
    return urllib.request.urlopen("http://kb-index:8080/search?q=" + q, timeout=5).read()


def batch_export(base_url: str):
    # ok: svcdesk-upstream-call-in-handler
    with urllib.request.urlopen(base_url + "/dora/metrics", timeout=60) as response:
        return response.read()


def helper_without_decorator(url: str):
    # ok: svcdesk-upstream-call-in-handler
    return urllib.request.urlopen(url, timeout=5)


def parse_body(raw: bytes):
    # ruleid: svcdesk-swallowed-exception
    try:
        return json.loads(raw)
    except Exception:
        return None


def observe_and_reraise(call):
    # ok: svcdesk-swallowed-exception
    try:
        return call()
    except Exception:
        status = 500
        raise


def specific_exception(raw: bytes):
    # ok: svcdesk-swallowed-exception
    try:
        return json.loads(raw)
    except ValueError:
        return None
