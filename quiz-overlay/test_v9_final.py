from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request

from common import Question
from overlay_server_v9_final import FINAL_QUIZ, OverlayServerV9Final
from quiz_engine_v9 import QuizEngineV9


def main() -> None:
    engine = QuizEngineV9()
    engine.set_questions([
        Question(
            kind='multiple',
            prompt='최종 문제 공개 HTML 검증',
            choices=['보기 1', '보기 2', '보기 3', '보기 4'],
            answer='2',
            accepted_answers=['NEVER-LEAK-ALIAS'],
            note='NEVER-LEAK-NOTE',
            auto_close_time=False,
        )
    ])
    engine.enter_practice(); assert engine.start_recruitment(); assert engine.close_recruitment(); assert engine.show_question()
    server = OverlayServerV9Final(engine, preferred_port=8905)
    server.start()
    try:
        time.sleep(.08)
        html = urllib.request.urlopen(server.quiz_url, timeout=3).read().decode('utf-8')
        assert '__INITIAL_STATE_JSON__' not in html
        assert 'const INITIAL={' in html
        assert '"state":"QUESTION_SHOWN"' in html
        assert 'NEVER-LEAK-ALIAS' not in html
        assert 'NEVER-LEAK-NOTE' not in html
        # Parse the actual bootstrap object instead of depending on whether
        # ensure_ascii encoded Korean text as literal characters or \u escapes.
        m = re.search(r'const INITIAL=(\{.*?\});let S=', html, re.S)
        assert m, 'bootstrapped INITIAL JSON missing'
        initial = json.loads(m.group(1))
        assert initial['state'] == 'QUESTION_SHOWN'
        assert initial['question']['prompt'] == '최종 문제 공개 HTML 검증'
        assert 'answer' not in initial['question']
        assert initial['correct'] == 0 and initial['firstCorrect'] == []

        scripts = re.findall(r'<script>(.*?)</script>', html, re.S)
        assert len(scripts) == 1
        node = shutil.which('node')
        if node:
            fd, path = tempfile.mkstemp(suffix='.js'); os.close(fd)
            try:
                with open(path, 'w', encoding='utf-8') as f: f.write(scripts[0])
                proc = subprocess.run([node, '--check', path], capture_output=True, text=True)
                if proc.returncode:
                    raise AssertionError(proc.stderr or proc.stdout)
            finally:
                try: os.unlink(path)
                except OSError: pass
    finally:
        server.stop()
    assert '연결 중' in FINAL_QUIZ
    assert 'apply(INITIAL)' in FINAL_QUIZ
    assert 'function topBar(s)' in FINAL_QUIZ
    assert 'function top(s)' not in FINAL_QUIZ
    print('v0.9 final bootstrap HTML/privacy/JS regression: PASS')


if __name__ == '__main__':
    main()
