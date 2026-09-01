from __future__ import annotations

import overlay_server_v9_release as release
from test_v9 import main as base_main


def main() -> None:
    base_main()
    assert 'padding:8px 10px' in release.QUIZ
    assert 'getBoundingClientRect' in release.QUIZ
    assert 'dataset.answerVisible' in release.QUIZ
    assert "r.bottom>window.innerHeight-1" in release.QUIZ
    print('v0.9 release viewport hotfix regression: PASS')


if __name__ == '__main__':
    main()
