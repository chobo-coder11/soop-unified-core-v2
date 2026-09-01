from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait


def _dump_failure(driver, screenshot: str, expected: str) -> None:
    try:
        metrics = driver.execute_script(
            """
            return {
              url: location.href,
              readyState: document.readyState,
              scene: document.body ? (document.body.dataset.scene || '') : '',
              overflow: document.body ? (document.body.dataset.overflow || '') : '',
              answerVisible: document.body ? (document.body.dataset.answerVisible || '') : '',
              bodyText: document.body ? document.body.innerText.slice(0,1000) : '',
              contentHTML: document.getElementById('content') ? document.getElementById('content').innerHTML.slice(0,2000) : '',
              scriptCount: document.scripts.length,
              initialType: typeof INITIAL,
              hasApply: typeof apply === 'function',
              hasEvents: typeof events === 'function'
            };
            """
        )
        print("BROWSER_TIMEOUT=" + json.dumps(metrics, ensure_ascii=False))
    except Exception as exc:
        print("BROWSER_TIMEOUT_METRICS_ERROR=" + repr(exc))
    try:
        for row in driver.get_log("browser"):
            print("BROWSER_CONSOLE=" + json.dumps(row, ensure_ascii=False))
    except Exception as exc:
        print("BROWSER_LOG_ERROR=" + repr(exc))
    try:
        Path(screenshot).parent.mkdir(parents=True, exist_ok=True)
        driver.save_screenshot(screenshot)
        print("BROWSER_TIMEOUT_SCREENSHOT=" + screenshot)
    except Exception as exc:
        print("BROWSER_SCREENSHOT_ERROR=" + repr(exc))
    try:
        src = driver.page_source
        print("BROWSER_SOURCE_HEAD=" + src[:3000].replace("\n", "\\n"))
    except Exception as exc:
        print("BROWSER_SOURCE_ERROR=" + repr(exc))
    print("BROWSER_EXPECTED_SCENE=" + expected)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("state")
    p.add_argument("width", type=int)
    p.add_argument("height", type=int)
    p.add_argument("screenshot")
    args = p.parse_args()

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--hide-scrollbars")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-background-networking")
    options.add_argument("--window-size=%d,%d" % (args.width, args.height))
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

    driver = webdriver.Chrome(options=options)
    try:
        driver.set_window_size(args.width, args.height)
        driver.get(args.url)
        try:
            WebDriverWait(driver, 8.0, poll_frequency=0.08).until(
                lambda d: d.execute_script("return document.body && document.body.dataset.scene") == args.state
            )
        except TimeoutException:
            _dump_failure(driver, args.screenshot, args.state)
            raise
        time.sleep(0.25)  # allow two RAF fit passes / font layout to settle
        metrics = driver.execute_script(
            """
            var card=document.getElementById('card');
            var body=document.body;
            var r=card?card.getBoundingClientRect():null;
            return {
              scene: body.dataset.scene || '',
              overflowFlag: body.dataset.overflow || '',
              answerVisible: body.dataset.answerVisible || '',
              innerWidth: window.innerWidth,
              innerHeight: window.innerHeight,
              bodyScrollWidth: document.documentElement.scrollWidth,
              bodyScrollHeight: document.documentElement.scrollHeight,
              card: r ? {left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height,scrollHeight:card.scrollHeight,clientHeight:card.clientHeight,className:card.className} : null,
              contentText: document.getElementById('content') ? document.getElementById('content').innerText.slice(0,500) : ''
            };
            """
        )
        print("BROWSER_METRICS=" + json.dumps(metrics, ensure_ascii=False))
        if metrics["scene"] != args.state:
            raise SystemExit("wrong scene: %r" % metrics["scene"])
        if not metrics["contentText"].strip():
            raise SystemExit("quiz content rendered empty")
        if metrics["overflowFlag"] != "0":
            raise SystemExit("overlay fit flag reports overflow")
        c = metrics["card"]
        if not c:
            raise SystemExit("quiz card missing")
        if c["left"] < -1 or c["top"] < -1 or c["right"] > metrics["innerWidth"] + 1 or c["bottom"] > metrics["innerHeight"] + 1:
            raise SystemExit("quiz card is outside viewport: %r" % c)
        expected_answer = "1" if args.state == "ANSWER_REVEALED" else "0"
        if metrics["answerVisible"] != expected_answer:
            raise SystemExit("wrong answer visibility: got %s expected %s" % (metrics["answerVisible"], expected_answer))
        if args.state == "QUESTION_SHOWN" and "아직 답변은 받지 않습니다" not in metrics["contentText"]:
            raise SystemExit("question preview guidance missing")
        if args.state == "ANSWERING" and "정답을 입력하세요" not in metrics["contentText"]:
            raise SystemExit("answering guidance missing")
        if args.state == "ANSWER_REVEALED" and "정답" not in metrics["contentText"]:
            raise SystemExit("answer reveal missing")
        Path(args.screenshot).parent.mkdir(parents=True, exist_ok=True)
        if not driver.save_screenshot(args.screenshot):
            raise SystemExit("screenshot failed")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
