import re
import time
from typing import Tuple, Optional

import requests
from bs4 import BeautifulSoup, Tag
from readability import Document

# --- Optional selenium imports (only needed for Selenium method) ---
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    SELENIUM_AVAILABLE = True
except Exception:
    SELENIUM_AVAILABLE = False


# -------------------------
# Helper: heuristically remove cookie banners/popups from a BeautifulSoup tree
# -------------------------
COOKIE_KEYWORDS = [
    "cookie", "consent", "gdpr", "agree", "accept", "privacy", "consenting", "opt-in", "optout",
    "dismiss", "reject", "cookiebar", "cookie-banner", "cookie-consent", "cookieNotice"
]


def _remove_cookie_like_nodes(soup: BeautifulSoup, max_removals: int = 20) -> int:
    """
    Heuristic removal of nodes that look like cookie banners/popups.
    Returns number of removed elements.
    """
    removed = 0
    # look for elements whose id/class/aria-label or visible text contains cookie keywords
    candidates = []
    for tag in soup.find_all(True):
        # inspect id/class/aria-label and role
        attrs_text = " ".join(
            [str(tag.get("id", "")), " ".join(tag.get("class", [])) if tag.get("class") else "", str(tag.get("aria-label", "")), str(tag.get("role", ""))]
        ).lower()
        if any(k in attrs_text for k in COOKIE_KEYWORDS):
            candidates.append(tag)
            continue
        # look for short text nodes that match cookie-like text
        try:
            text = tag.get_text(" ", strip=True).lower()
        except Exception:
            text = ""
        if len(text) > 0 and any(k in text for k in COOKIE_KEYWORDS) and len(text) < 400:
            candidates.append(tag)

    # Remove largest matching candidates first (likely wrapper divs)
    candidates = sorted(set(candidates), key=lambda t: -len(t.get_text(" ", strip=True)))
    for tag in candidates[:max_removals]:
        try:
            tag.decompose()
            removed += 1
        except Exception:
            pass
    return removed


# -------------------------
# Main: requests + readability approach
# -------------------------
def fetch_main_content_requests(url: str, headers: Optional[dict] = None, timeout: int = 15) -> Tuple[str, str]:
    """
    Fetch page using requests, try to remove cookie banners heuristically,
    then return (main_html_fragment, cleaned_full_html).
    main_html_fragment: the HTML snippet representing the main content (from Readability)
    cleaned_full_html: the original page HTML with cookie nodes removed where possible
    """
    headers = headers or {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0 Safari/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    html = resp.text

    # parse and attempt to remove cookie-like nodes
    soup = BeautifulSoup(html, "lxml")
    removed = _remove_cookie_like_nodes(soup)

    cleaned_html = str(soup)

    # Remove layout elements
    for tag in soup(["nav", "header", "footer", "aside", "script", "style"]):
        tag.decompose()

    # Check and get main section of the pages
    main = soup.find("main")

    if not main:
        
        # fallback method, if no 'main' section in html page
        candidates = soup.find_all("div", recursive=True)
        main = max(candidates, key=lambda c: len(c.get_text(strip=True)), default=soup.body)

    # Get cleaned HTML content. Tags retained
    main_html = str(main)

    # run readability on cleaned html to get main content HTML
    # doc = Document(cleaned_html)
    # main_html = doc.summary(html_partial=True)  # main HTML fragment
    
    return main_html, cleaned_html


# -------------------------
# Selenium approach (click cookie buttons where possible)
# -------------------------
def fetch_main_content_selenium(url: str, headless: bool = True, wait_seconds: int = 8) -> Tuple[str, str]:
    """
    Launch headless Chrome, try to click cookie/consent buttons, wait for page to stabilize,
    then return (main_html_fragment, cleaned_full_html).
    Requires selenium + webdriver-manager installed.
    """
    if not SELENIUM_AVAILABLE:
        raise RuntimeError("Selenium or webdriver-manager is not installed. Please `pip install selenium webdriver-manager`.")

    opts = ChromeOptions()
    if headless:
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")

    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    try:
        driver.get(url)
        wait = WebDriverWait(driver, wait_seconds)

        # Strategy: attempt a few common patterns to find and click cookie buttons.
        # This is best-effort and covers many sites.
        click_selectors = [
            # common button text
            ("xpath", "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]"),
            ("xpath", "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree')]"),
            ("xpath", "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'allow')]"),
            ("xpath", "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'got it')]"),
            ("xpath", "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'yes')]"),
            ("xpath", "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]"),
            # aria labels / role
            ("css", "button[aria-label*='accept']"),
            ("css", "button[aria-label*='consent']"),
        ]

        # Additional heuristics: search for elements that contain 'cookie' in class/id/text then click descendant buttons/inputs/labels
        # try clicking several times with a short wait in between
        for method, selector in click_selectors:
            try:
                if method == "xpath":
                    elems = driver.find_elements(By.XPATH, selector)
                else:
                    elems = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elems:
                    try:
                        # scroll into view and click via JS if necessary
                        driver.execute_script("arguments[0].scrollIntoView(true);", el)
                        time.sleep(0.1)
                        try:
                            el.click()
                        except Exception:
                            driver.execute_script("arguments[0].click();", el)
                        time.sleep(0.3)
                    except Exception:
                        pass
            except Exception:
                pass

        # Additionally, attempt to find elements that have 'cookie' in id/class and click child buttons/inputs
        try:
            cookie_containers = driver.find_elements(By.XPATH, "//*[contains(translate(@id, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cookie') or contains(translate(@class, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cookie') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cookie') ]")
            for c in cookie_containers:
                try:
                    # find buttons inside
                    buttons = c.find_elements(By.XPATH, ".//button|.//a|.//input")
                    for b in buttons:
                        try:
                            driver.execute_script("arguments[0].scrollIntoView(true);", b)
                            b.click()
                            time.sleep(0.2)
                        except Exception:
                            try:
                                driver.execute_script("arguments[0].click();", b)
                            except Exception:
                                pass
                except Exception:
                    pass
        except Exception:
            pass

        # give time for JS to settle
        time.sleep(1.2)
        # final wait for ready state complete
        try:
            wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        except Exception:
            pass

        page_source = driver.page_source
        # Clean HTML on the client side too (remove cookie nodes heuristically)
        soup = BeautifulSoup(page_source, "lxml")
        _remove_cookie_like_nodes(soup)
        cleaned_html = str(soup)

        # Remove layout elements
        for tag in soup(["nav", "header", "footer", "aside", "script", "style"]):
            tag.decompose()

        # Check and get main section of the pages
        main = soup.find("main")

        if not main:
            
            # fallback method, if no 'main' section in html page
            candidates = soup.find_all("div", recursive=True)
            main = max(candidates, key=lambda c: len(c.get_text(strip=True)), default=soup.body)

        # Get cleaned HTML content. Tags retained
        main_html = str(main)

        # Extract main content via Readability
        # doc = Document(cleaned_html)
        # main_html = doc.summary(html_partial=True)
        return main_html, cleaned_html
    finally:
        driver.quit()


# -------------------------
# Unified wrapper
# -------------------------
def fetch_main_content(url: str, method: str = "auto", **kwargs) -> Tuple[str, str]:
    """
    Unified function.
    method = "auto" (try requests then selenium if failure),
             "requests" (use requests/readability),
             "selenium" (use selenium webdriver).
    Returns (main_html_fragment, cleaned_full_html)
    """
    method = method.lower()
    if method not in ("auto", "requests", "selenium"):
        raise ValueError("method must be one of 'auto', 'requests', 'selenium', 'auto'")

    # try requests first if auto
    if method in ("auto", "requests"):
        try:
            return fetch_main_content_requests(url, **kwargs)
        except Exception as e:
            if method == "requests":
                raise
            # else fallthrough to selenium
            last_exc = e

    # use selenium
    if not SELENIUM_AVAILABLE:
        raise RuntimeError("Selenium not available; install selenium and webdriver-manager if you need JS interaction.")
    return fetch_main_content_selenium(url, **kwargs)


if __name__ == "__main__":
    test_url = "https://www.spiceworks.com/tech/tech-general/articles/what-are-embedded-systems/"
    # try auto (requests first, then selenium if needed)
    try:
        main_fragment, full_html = fetch_main_content(test_url, method="auto")
        
        with open ('main.html', mode='w', encoding='utf-8') as f:
            print("Main fragment length:", len(main_fragment))
            print("First 400 chars of main fragment:\n", main_fragment[:400])

            print (main_fragment, file=f)

        with open ('full.html', mode='w', encoding='utf-8') as f:
            print("full html length:", len(full_html))
            print("First 400 chars of full html:\n", full_html[:400])

            print (full_html, file=f)

    except Exception as ex:
        print("Error:", ex)
