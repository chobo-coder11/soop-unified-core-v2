from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait


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

    driver = webdriver.Chrome(options=options)
    try:
        driver.set_window_size(args.width, args.height)
        driver.get(args.url)
        WebDriverWait(driver, 8.0, poll_frequency=0.08).until(
            lambda d: d.execute_script("return document.body && document.body.dataset.scene") == args.state
        )
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
