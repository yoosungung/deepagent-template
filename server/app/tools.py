import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

from langchain_core.tools import tool

from app.config import settings

logger = logging.getLogger(__name__)

NAVER_WEB_SEARCH_URL = "https://openapi.naver.com/v1/search/webkr.json"
DEFAULT_DISPLAY = 10


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def _search_naver(query: str, display: int = DEFAULT_DISPLAY) -> str:
    if not settings.NAVER_CLIENT_ID or not settings.NAVER_CLIENT_SECRET:
        return (
            "Naver 검색 API 인증 정보가 설정되지 않았습니다. "
            "NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET 환경 변수를 설정해 주세요."
        )

    params = urllib.parse.urlencode(
        {"query": query, "display": display, "start": 1}
    )
    url = f"{NAVER_WEB_SEARCH_URL}?{params}"
    request = urllib.request.Request(
        url,
        headers={
            "X-Naver-Client-Id": settings.NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": settings.NAVER_CLIENT_SECRET,
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logger.error("Naver search HTTP error %s: %s", exc.code, body)
        return f"Naver 검색 API 오류 (HTTP {exc.code}): {body}"
    except urllib.error.URLError as exc:
        logger.error("Naver search request failed: %s", exc)
        return f"Naver 검색 요청 실패: {exc.reason}"

    items = data.get("items", [])
    if not items:
        return f"'{query}'에 대한 Naver 검색 결과가 없습니다."

    total = data.get("total", 0)
    lines = [
        f"Naver 웹 검색 결과: '{query}' (총 {total}건 중 {len(items)}건 표시)\n"
    ]
    for index, item in enumerate(items, start=1):
        title = _strip_html(item.get("title", ""))
        link = item.get("link", "")
        description = _strip_html(item.get("description", ""))
        lines.append(f"{index}. {title}\n   URL: {link}\n   {description}\n")

    return "\n".join(lines)


@tool
def web_search(query: str) -> str:
    """Search the web using Naver for information about specific technologies, requirements, or templates.

    Always pass the query in Korean.

    Args:
        query: The search query (Korean only).
    """
    logger.info("Executing Naver web search with query: %s", query)
    return _search_naver(query)
