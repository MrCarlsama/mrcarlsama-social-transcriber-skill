from __future__ import annotations

import hashlib
import http.cookiejar
import time
import urllib.request
from pathlib import Path


PUBLIC_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def is_fresh_cookie_error(error: BaseException | str) -> bool:
    text = str(error).lower()
    return "fresh cookies" in text or "cookie" in text


def platform_from_url(url: str) -> str:
    lower = url.lower()
    if "douyin.com" in lower or "v.douyin.com" in lower or "iesdouyin.com" in lower:
        return "douyin"
    if "xiaohongshu.com" in lower or "xhslink.com" in lower:
        return "xiaohongshu"
    return "unknown"


def generate_public_visitor_cookies(url: str, cookie_dir: Path) -> Path:
    cookie_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{url}:{time.time()}".encode("utf-8")).hexdigest()[:12]
    target = cookie_dir / f"{platform_from_url(url)}-{key}.cookies.txt"

    errors: list[str] = []
    for generator in (_generate_with_playwright, _generate_with_http):
        try:
            generator(url, target)
            if _has_cookie_rows(target):
                return target
        except Exception as exc:
            errors.append(f"{generator.__name__}: {type(exc).__name__}: {exc}")

    detail = "; ".join(errors) if errors else "no cookies were produced"
    raise RuntimeError(f"failed to generate public visitor cookies: {detail}")


def _generate_with_playwright(url: str, target: Path) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = None
        launch_errors: list[str] = []
        for channel in ("chrome", "msedge"):
            try:
                browser = playwright.chromium.launch(channel=channel, headless=True)
                break
            except Exception as exc:
                launch_errors.append(f"{channel}: {exc}")
        if browser is None:
            try:
                browser = playwright.chromium.launch(headless=True)
            except Exception as exc:
                launch_errors.append(f"bundled chromium: {exc}")
                raise RuntimeError("; ".join(launch_errors)) from exc

        try:
            context = browser.new_context(
                user_agent=PUBLIC_USER_AGENT,
                locale="zh-CN",
                viewport={"width": 1280, "height": 720},
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(5_000)
            _write_netscape_cookie_file(target, context.cookies())
        finally:
            browser.close()


def _generate_with_http(url: str, target: Path) -> None:
    jar = http.cookiejar.MozillaCookieJar(str(target))
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": PUBLIC_USER_AGENT,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    with opener.open(request, timeout=25) as response:
        response.read(128 * 1024)
    jar.save(ignore_discard=True, ignore_expires=True)


def _write_netscape_cookie_file(target: Path, cookies: list[dict]) -> None:
    lines = [
        "# Netscape HTTP Cookie File",
        "# Generated from an isolated public browser context.",
        "# This file does not contain cookies read from the user's browser profile.",
        "",
    ]
    for cookie in cookies:
        name = str(cookie.get("name") or "")
        if not name:
            continue
        domain = str(cookie.get("domain") or "")
        include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
        path = str(cookie.get("path") or "/")
        secure = "TRUE" if cookie.get("secure") else "FALSE"
        expires = int(cookie.get("expires") or 0)
        if expires < 0:
            expires = 0
        value = str(cookie.get("value") or "")
        lines.append(f"{domain}\t{include_subdomains}\t{path}\t{secure}\t{expires}\t{name}\t{value}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _has_cookie_rows(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line and not line.startswith("#"):
            return True
    return False
