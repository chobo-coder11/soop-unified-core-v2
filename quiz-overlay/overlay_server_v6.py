from __future__ import annotations

import overlay_server_v5 as v5
from overlay_server_v5 import OverlayServerV5

from quiz_engine_v6 import QuizEngineV6


POLISH = r'''
/* v0.6 visual system: layout hierarchy changes without expensive filters */
:root{--radius-xl:34px;--radius-lg:20px;--radius-md:14px;--pad-x:clamp(24px,2.3vw,40px)}
.surface{position:relative;overflow:hidden}
.surface:before{content:"";position:absolute;inset:0 auto 0 0;width:5px;background:var(--accent);opacity:.9}
.card,.panel{isolation:isolate}
.card{padding:34px var(--pad-x)!important;border-radius:var(--radius-xl)!important}
.top{padding-bottom:14px;border-bottom:1px solid var(--line);margin-bottom:24px!important}
.eyebrow{letter-spacing:.12em!important;text-transform:uppercase}
.chip{border-radius:12px!important;padding:9px 13px!important;background:var(--panel)!important}
.q{max-width:1320px;line-height:1.16!important;text-wrap:balance}
.choices{gap:14px!important;margin-top:28px!important}
.choice{position:relative;border-radius:var(--radius-lg)!important;min-height:86px!important;padding:17px 20px!important;transition:transform .18s ease,border-color .18s ease,background-color .18s ease}
.choice .n,.n{border-radius:13px!important;background:var(--surface)!important}
.choice.correct{transform:translateY(-1px)}
.foot{padding-top:18px;border-top:1px solid var(--line)}
.instruction{letter-spacing:-.02em}
.timer{min-width:150px;text-align:right}
.bar{height:8px!important;margin-top:14px!important}
.hero{padding:54px 20px!important}
.hero .k{margin-bottom:10px}
.hero .t{text-wrap:balance}
.fast span{border-radius:14px!important;padding:9px 13px!important}
.warn{border-radius:14px!important}

/* Clean = restrained broadcast-card */
body.style-clean .surface{background:var(--surface)}
body.style-clean .card{box-shadow:0 22px 55px rgba(0,0,0,.24)}

/* Game Show = stronger frame, bolder hierarchy */
body.style-game .surface:before{width:8px;background:linear-gradient(180deg,var(--accent),var(--gold))}
body.style-game .card{border-width:2px;box-shadow:0 24px 58px rgba(0,0,0,.30)}
body.style-game .eyebrow{color:var(--gold)!important}
body.style-game .choice{border-width:2px;background:rgba(255,179,41,.055)}
body.style-game .n{color:#111;background:var(--gold)!important;border-color:transparent!important}
body.style-game .hero .t{color:var(--gold)}

/* Neon = high contrast but no blur-heavy effects */
body.style-neon .surface{border-color:rgba(139,108,255,.52)!important;box-shadow:0 0 0 1px rgba(139,108,255,.14),0 24px 62px rgba(0,0,0,.42)!important}
body.style-neon .surface:before{width:6px;background:linear-gradient(180deg,#b7a4ff,#7354ff)}
body.style-neon .choice{background:rgba(139,108,255,.075);border-color:rgba(139,108,255,.25)}
body.style-neon .chip{background:rgba(139,108,255,.10)!important}

/* Minimal = almost typography-only, works well over gameplay */
body.style-minimal .surface{background:rgba(8,10,15,.78)!important;border-color:rgba(255,255,255,.09)!important;box-shadow:none!important}
body.style-minimal .surface:before{width:3px;opacity:.75}
body.style-minimal .card{padding:28px 32px!important;border-radius:18px!important}
body.style-minimal .choice{background:rgba(255,255,255,.045);border-radius:12px!important;min-height:70px!important}
body.style-minimal .top{border-bottom:0;margin-bottom:15px!important;padding-bottom:0}
body.style-minimal .foot{border-top:0;padding-top:6px}

/* Ranking treatment */
.panel{border-radius:28px!important;padding:24px 26px!important}
.rows{gap:8px!important}
.row{position:relative;border-radius:15px!important;padding:11px 13px!important}
.row:nth-child(1){border-color:rgba(241,195,91,.55)!important;background:rgba(241,195,91,.09)!important}
.row:nth-child(2){background:rgba(180,190,205,.08)!important}
.row:nth-child(3){background:rgba(190,127,76,.075)!important}
.row:nth-child(-n+3) .rank{font-size:1.08em}

/* Status / compact overlays */
.status,.podium{border-radius:24px!important}

@media(max-width:900px){.card{padding:22px!important}.choice{min-height:68px!important}.surface:before{width:3px}.top{align-items:flex-start;flex-direction:column}.chips{flex-wrap:wrap}}
'''

RANK_POLISH = r'''
.head{padding-bottom:13px;border-bottom:1px solid var(--line);margin-bottom:14px!important}.title{letter-spacing:-.055em!important}.value{font-variant-numeric:tabular-nums}
'''


def _inject(html: str, css: str) -> str:
    if "</style>" not in html:
        return html
    return html.replace("</style>", css + "\n</style>", 1)


# Patch only presentation strings in the v5 server module. Networking/SSE routing
# and engine state semantics remain unchanged and therefore keep v0.5 stability.
v5.QUIZ = _inject(v5.QUIZ, POLISH)
v5.RANK = _inject(v5.RANK, POLISH + RANK_POLISH)
if hasattr(v5, "TOP3"):
    v5.TOP3 = _inject(v5.TOP3, POLISH + RANK_POLISH)
if hasattr(v5, "STATUS"):
    v5.STATUS = _inject(v5.STATUS, POLISH)


class OverlayServerV6(OverlayServerV5):
    def __init__(self, engine: QuizEngineV6, preferred_port: int = 8765) -> None:
        super().__init__(engine, preferred_port)
