from __future__ import annotations

import overlay_server_v5 as v5
import overlay_server_v6  # noqa: F401 - keep v0.6 structural polish injected first
from overlay_server_v6 import OverlayServerV6

from quiz_engine_v7 import QuizEngineV7


V7_POLISH = r'''
/* v0.7 broadcast readability + motion system */
:root{--v7-fast:.18s;--v7-base:.32s;--v7-slow:.52s}
html,body{font-family:"Malgun Gothic","Segoe UI Variable","Segoe UI",sans-serif!important}
.card{width:min(95vw,1560px)!important;padding:clamp(30px,2.5vw,46px) clamp(30px,3vw,52px)!important}
.top{margin-bottom:clamp(20px,2vw,30px)!important}
.eyebrow{font-size:clamp(17px,1.35vw,25px)!important;font-weight:900!important}
.chip{font-size:clamp(16px,1.15vw,22px)!important;padding:10px 14px!important}
.q{font-size:clamp(42px,4.2vw,78px)!important;line-height:1.14!important;letter-spacing:-.048em!important}
.choices{gap:clamp(14px,1.3vw,20px)!important;margin-top:clamp(26px,2.3vw,38px)!important}
.choice{min-height:clamp(88px,8vh,112px)!important;padding:18px 22px!important;font-size:clamp(26px,2.2vw,40px)!important;font-weight:820!important}
.choice .n,.n{width:48px!important;height:48px!important;flex-basis:48px!important;font-size:.82em!important}
.instruction{font-size:clamp(25px,2vw,37px)!important;line-height:1.2!important}
.hint{font-size:clamp(16px,1.25vw,23px)!important;margin-top:8px!important}
.timer{font-size:clamp(46px,4vw,70px)!important;min-width:180px!important}
.bar{height:10px!important;margin-top:16px!important}
.hero{padding:clamp(48px,5vw,76px) 18px!important}
.hero .k{font-size:clamp(18px,1.45vw,27px)!important}
.hero .t{font-size:clamp(72px,8vw,138px)!important;line-height:.96!important}
.hero .s{font-size:clamp(23px,2vw,38px)!important;line-height:1.35!important}
.answer{font-size:clamp(62px,6.8vw,116px)!important;line-height:1.03!important}
.fast span{font-size:clamp(16px,1.15vw,22px)!important;padding:11px 15px!important}
.warn{font-size:clamp(16px,1vw,20px)!important;padding:14px 18px!important}

/* scene motion: short, readable, GPU-cheap */
.enter{animation:v7-enter var(--v7-base) cubic-bezier(.2,.8,.2,1) both!important}
.pop{animation:v7-pop var(--v7-base) cubic-bezier(.2,.86,.2,1.08) both!important}
.choices .choice{animation:v7-choice var(--v7-base) cubic-bezier(.2,.78,.2,1) both}
.choices .choice:nth-child(2){animation-delay:.045s}.choices .choice:nth-child(3){animation-delay:.09s}.choices .choice:nth-child(4){animation-delay:.135s}.choices .choice:nth-child(5){animation-delay:.18s}.choices .choice:nth-child(6){animation-delay:.225s}
.choice.correct{animation:v7-correct .48s cubic-bezier(.2,.8,.2,1) both!important}
@keyframes v7-enter{from{opacity:0;transform:translate3d(0,20px,0)}to{opacity:1;transform:translate3d(0,0,0)}}
@keyframes v7-pop{0%{opacity:0;transform:scale(.91)}75%{opacity:1;transform:scale(1.025)}100%{opacity:1;transform:scale(1)}}
@keyframes v7-choice{from{opacity:0;transform:translate3d(18px,0,0)}to{opacity:1;transform:translate3d(0,0,0)}}
@keyframes v7-correct{0%{transform:scale(.985)}55%{transform:scale(1.018);border-color:var(--good)}100%{transform:scale(1);border-color:var(--good)}}
.no-motion *{animation:none!important;transition:none!important}

/* theme personalities are structural, not just recolors */
body.style-clean .surface{border-radius:30px!important}
body.style-clean .choice{background:rgba(255,255,255,.052)!important}
body.light.style-clean .choice{background:rgba(17,24,39,.045)!important}

body.style-game .card{border-radius:38px!important;padding-top:42px!important}
body.style-game .top{border-bottom:2px solid rgba(255,202,80,.28)!important;padding-bottom:18px!important}
body.style-game .q{text-align:center;max-width:1400px;margin-inline:auto}
body.style-game .choices{max-width:1360px;margin-left:auto!important;margin-right:auto!important}
body.style-game .choice{min-height:102px!important;border-radius:24px!important}
body.style-game .instruction{text-transform:none;letter-spacing:-.03em}

body.style-neon .card{border-radius:26px!important}
body.style-neon .q{color:#f5f2ff;text-shadow:0 2px 0 rgba(0,0,0,.12)}
body.style-neon .choice{border-left-width:4px!important}
body.style-neon .choice.correct{background:rgba(66,202,138,.14)!important}

body.style-minimal .card{max-width:1440px!important;padding:24px 30px!important}
body.style-minimal .q{font-size:clamp(38px,3.7vw,68px)!important}
body.style-minimal .choice{min-height:76px!important;font-size:clamp(22px,1.9vw,34px)!important;padding:13px 17px!important}
body.style-minimal .hero{padding:36px 12px!important}
body.style-minimal .hero .t{font-size:clamp(62px,6.8vw,116px)!important}

/* ranking readability */
.panel{width:min(95vw,860px)!important;padding:28px 30px!important}
.title{font-size:clamp(38px,3.5vw,58px)!important}
.sub{font-size:clamp(15px,1.15vw,21px)!important}
.rows{gap:10px!important}
.row{grid-template-columns:58px minmax(0,1fr) 150px!important;min-height:58px;padding:13px 15px!important;border-radius:18px!important;animation:v7-rank-in .28s ease both}
.row:nth-child(2){animation-delay:.025s}.row:nth-child(3){animation-delay:.05s}.row:nth-child(4){animation-delay:.075s}.row:nth-child(5){animation-delay:.1s}
.rank{font-size:clamp(23px,2vw,31px)!important}.name{font-size:clamp(19px,1.6vw,26px)!important}.value{font-size:clamp(18px,1.45vw,24px)!important}
.row:nth-child(1){min-height:68px!important;transform-origin:center}
@keyframes v7-rank-in{from{opacity:0;transform:translate3d(0,8px,0)}to{opacity:1;transform:translate3d(0,0,0)}}

/* small-height broadcast canvases */
@media(max-height:760px){
 .card{padding:24px 30px!important}.q{font-size:clamp(34px,3.6vw,62px)!important}.choice{min-height:66px!important;font-size:clamp(21px,1.8vw,32px)!important;padding:11px 16px!important}.choice .n,.n{width:40px!important;height:40px!important;flex-basis:40px!important}.foot{margin-top:15px!important}.hero{padding:28px 12px!important}.hero .t{font-size:clamp(58px,6.5vw,108px)!important}
}
@media(max-width:900px){.q{text-wrap:pretty}.choices{grid-template-columns:1fr!important}.timer{text-align:left!important}}
'''


def _inject(html: str, css: str) -> str:
    if "</style>" not in html:
        return html
    return html.replace("</style>", css + "\n</style>", 1)


for name in ("QUIZ", "RANK", "TOP3", "STATUS"):
    if hasattr(v5, name):
        setattr(v5, name, _inject(getattr(v5, name), V7_POLISH))


class OverlayServerV7(OverlayServerV6):
    def __init__(self, engine: QuizEngineV7, preferred_port: int = 8765) -> None:
        super().__init__(engine, preferred_port)
