from __future__ import annotations

import json
import socket
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from quiz_engine import QuizEngine


COMMON_STYLE = r'''
:root{--bg:rgba(12,15,22,.92);--panel:rgba(19,23,33,.95);--text:#f7f9fc;--muted:#aeb7c8;--line:rgba(255,255,255,.12);--soft:rgba(255,255,255,.07);--accent:#75a7ff;--good:#66d59a;--bad:#ff7c88;--gold:#ffd56a;--shadow:0 24px 70px rgba(0,0,0,.34)}
body.light{--bg:rgba(249,250,252,.94);--panel:rgba(255,255,255,.96);--text:#141821;--muted:#626c7d;--line:rgba(20,24,33,.12);--soft:rgba(20,24,33,.055);--accent:#326dff;--good:#168957;--bad:#d43d4d;--gold:#a66c00;--shadow:0 22px 60px rgba(26,35,52,.18)}
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;background:transparent;overflow:hidden;font-family:"Segoe UI","Malgun Gothic","Apple SD Gothic Neo",sans-serif;color:var(--text)}
.shell{width:100%;height:100%;display:flex;align-items:center;justify-content:center;padding:3.3vw}.surface{background:var(--bg);border:1px solid var(--line);box-shadow:var(--shadow);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px)}
.fade-in{animation:fadeIn .34s cubic-bezier(.2,.8,.2,1) both}.pop{animation:pop .48s cubic-bezier(.18,.9,.28,1.22) both}.slide-up{animation:slideUp .4s cubic-bezier(.2,.8,.2,1) both}
.no-motion *{animation:none!important;transition:none!important}@keyframes fadeIn{from{opacity:0}to{opacity:1}}@keyframes pop{0%{opacity:0;transform:scale(.86)}100%{opacity:1;transform:scale(1)}}@keyframes slideUp{from{opacity:0;transform:translateY(24px)}to{opacity:1;transform:translateY(0)}}
'''

QUIZ_HTML = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>''' + COMMON_STYLE + r'''
.card{width:min(92vw,1480px);border-radius:30px;padding:34px 42px}.header{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:22px}.eyebrow{font-size:clamp(18px,1.45vw,26px);font-weight:800;color:var(--muted);letter-spacing:.02em}.badge{display:inline-flex;align-items:center;gap:8px;border:1px solid var(--line);background:var(--soft);padding:9px 14px;border-radius:999px;font-size:clamp(16px,1.2vw,22px);font-weight:800}.dot{width:9px;height:9px;border-radius:50%;background:var(--good)}.question{font-size:clamp(34px,4vw,70px);font-weight:900;line-height:1.2;letter-spacing:-.025em;word-break:keep-all}.choices{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:27px}.choice{position:relative;display:flex;align-items:flex-start;gap:16px;min-height:86px;padding:18px 22px;border:1px solid var(--line);background:var(--soft);border-radius:18px;font-size:clamp(23px,2.15vw,39px);font-weight:780;line-height:1.25}.choice.correct{border-color:color-mix(in srgb,var(--good) 75%,transparent);background:color-mix(in srgb,var(--good) 16%,transparent)}.choice-no{display:flex;align-items:center;justify-content:center;flex:0 0 auto;width:42px;height:42px;border-radius:12px;background:var(--panel);border:1px solid var(--line);font-weight:900}.footer{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-top:25px}.instruction{font-size:clamp(22px,2vw,37px);font-weight:900}.hint{color:var(--muted);font-size:clamp(17px,1.25vw,23px);font-weight:720}.timer{min-width:126px;text-align:right;font-size:clamp(30px,3.1vw,54px);font-variant-numeric:tabular-nums;font-weight:950}.progress{height:7px;border-radius:999px;background:var(--soft);overflow:hidden;margin-top:13px}.progress>i{display:block;height:100%;width:100%;background:var(--accent);border-radius:inherit;transition:width .16s linear}.hero{text-align:center;padding:36px 20px}.hero-title{font-size:clamp(62px,8.8vw,148px);font-weight:950;letter-spacing:-.035em;line-height:.95}.hero-sub{margin-top:22px;font-size:clamp(23px,2.2vw,40px);font-weight:820;color:var(--muted)}.count{color:var(--accent);font-variant-numeric:tabular-nums}.answer-label{text-align:center;color:var(--muted);font-size:clamp(21px,1.8vw,31px);font-weight:800}.answer{text-align:center;font-size:clamp(50px,6.5vw,108px);font-weight:950;line-height:1.05;margin:10px 0 18px}.fastest{display:flex;justify-content:center;gap:12px;flex-wrap:wrap;margin-top:20px}.fast-chip{padding:10px 15px;border-radius:14px;border:1px solid var(--line);background:var(--soft);font-size:clamp(16px,1.15vw,22px);font-weight:760}.warn{position:absolute;left:2vw;bottom:2vw;max-width:min(70vw,920px);padding:11px 16px;border-radius:12px;background:rgba(158,44,56,.94);color:white;font-size:16px;font-weight:760;box-shadow:0 12px 32px rgba(0,0,0,.25)}.hidden{display:none}@media(max-width:900px){.choices{grid-template-columns:1fr}.card{padding:25px}.footer{align-items:flex-end}.choice{min-height:70px}}
</style></head><body><div class="shell"><div id="card" class="card surface"><div id="content"></div></div></div><div id="warn" class="warn hidden"></div><script>
const $=s=>document.querySelector(s);let previousKey='',lastParticipants=0;
function esc(v){return String(v??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function visual(s){document.body.classList.toggle('light',s.visual?.theme==='light');document.body.classList.toggle('no-motion',s.visual?.motion===false)}
function animateNumber(from,to,el){if(document.body.classList.contains('no-motion')){el.textContent=to.toLocaleString();return}const st=performance.now(),dur=340;function f(t){const p=Math.min(1,(t-st)/dur),e=1-Math.pow(1-p,3);el.textContent=Math.round(from+(to-from)*e).toLocaleString();if(p<1)requestAnimationFrame(f)}requestAnimationFrame(f)}
function choices(q,correct){if(q.kind==='multiple')return '<div class="choices">'+q.choices.map((v,i)=>'<div class="choice '+(String(i+1)===String(correct)?'correct':'')+'"><span class="choice-no">'+(i+1)+'</span><span>'+esc(v)+'</span></div>').join('')+'</div>';if(q.kind==='ox')return '<div class="choices"><div class="choice '+(correct==='O'?'correct':'')+'"><span class="choice-no">O</span><span>맞다</span></div><div class="choice '+(correct==='X'?'correct':'')+'"><span class="choice-no">X</span><span>아니다</span></div></div>';return ''}
function top(s){return '<div class="header"><div class="eyebrow">Q'+(s.questionIndex+1)+' / '+s.questionCount+'</div><div class="badge"><span class="dot"></span> 참가 '+s.participants.toLocaleString()+'명</div></div>'}
function render(s){visual(s);const c=$('#content'),q=s.question,key=s.state+':'+s.questionIndex;$('#warn').classList.toggle('hidden',!s.integrityWarning);$('#warn').textContent=s.integrityWarning||'';
if(s.state==='DISCONNECTED'||s.state==='READY'){c.innerHTML='<div class="hero fade-in"><div class="hero-title">SOOP QUIZ</div><div class="hero-sub">진행자 프로그램에서 시작해주세요</div></div>';return}
if(s.state==='RECRUITING'){c.innerHTML='<div class="hero '+(key!==previousKey?'pop':'')+'"><div class="hero-title">참가 모집</div><div class="hero-sub">채팅에 <b>!참여</b> 를 입력하세요</div><div class="hero-sub">현재 <span id="pc" class="count">'+s.participants.toLocaleString()+'</span>명 참여</div></div>';const el=$('#pc');if(el&&s.participants!==lastParticipants)animateNumber(lastParticipants,s.participants,el);lastParticipants=s.participants;previousKey=key;return}
if(s.state==='LOCKED'){c.innerHTML='<div class="hero fade-in"><div class="hero-title">READY</div><div class="hero-sub">참가자 '+s.participants.toLocaleString()+'명 · 다음 문제를 준비합니다</div></div>';previousKey=key;return}
if(!q){c.innerHTML='<div class="hero"><div class="hero-title">QUIZ</div></div>';return}
if(s.state==='QUESTION_SHOWN'){c.innerHTML=top(s)+'<div class="question slide-up">'+esc(q.prompt)+'</div>'+choices(q,'')+'<div class="footer"><div><div class="instruction">문제를 확인해주세요</div><div class="hint">START가 나온 뒤에만 답변이 인정됩니다</div></div><div class="badge">답변 대기</div></div>';previousKey=key;return}
if(s.state==='ANSWERING'){const sec=s.remainingMs==null?'':(s.remainingMs/1000).toFixed(1);const pct=s.remainingMs==null?100:Math.max(0,Math.min(100,s.remainingMs/(Math.max(1,q.duration_sec)*1000)*100));c.innerHTML=top(s)+'<div class="question">'+esc(q.prompt)+'</div>'+choices(q,'')+'<div class="footer"><div><div class="instruction">'+(key!==previousKey?'<span class="pop" style="display:inline-block;color:var(--accent);margin-right:14px">START!</span>':'')+'정답을 입력해주세요</div><div class="hint">'+esc(s.answerHint||'')+'</div></div><div class="timer">'+sec+'<span style="font-size:.46em;color:var(--muted)">초</span></div></div><div class="progress"><i style="width:'+pct+'%"></i></div>';previousKey=key;return}
if(s.state==='QUESTION_CLOSED'){c.innerHTML=top(s)+'<div class="question">'+esc(q.prompt)+'</div>'+choices(q,'')+'<div class="hero pop" style="padding:30px 10px 12px"><div class="hero-title" style="font-size:clamp(52px,6vw,100px)">마감!</div><div class="hero-sub">총 '+s.answered.toLocaleString()+'명 답변 · 정답 공개를 기다려주세요</div></div>';previousKey=key;return}
if(s.state==='ANSWER_REVEALED'){let ans=esc(q.answer);if(q.kind==='multiple'){const idx=Number(q.answer)-1;ans=esc(q.answer)+'. '+esc(q.choices[idx]||'')}const fastest=(s.visual?.showFastest!==false?s.firstCorrect.slice(0,3):[]).map(x=>'<div class="fast-chip">'+x.rank+'위 '+esc(x.display)+' · '+(x.elapsedMs/1000).toFixed(3)+'초</div>').join('');c.innerHTML=top(s)+'<div class="answer-label">정답은</div><div class="answer pop">'+ans+'</div>'+choices(q,String(q.answer))+'<div class="footer"><div><div class="instruction">정답자 '+s.correct.toLocaleString()+'명</div><div class="hint">정답률 '+(s.answered?((s.correct/s.answered)*100).toFixed(1):'0.0')+'%</div></div></div><div class="fastest">'+fastest+'</div>';previousKey=key;return}
if(s.state==='FINISHED'){c.innerHTML='<div class="hero pop"><div class="hero-title">QUIZ END</div><div class="hero-sub">최종 TOP 10을 확인해주세요</div></div>';previousKey=key;return}}
async function tick(){try{const r=await fetch('/api/state?ts='+Date.now(),{cache:'no-store'});render(await r.json())}catch(e){}setTimeout(tick,160)}tick();
</script></body></html>'''

RANK_HTML = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>''' + COMMON_STYLE + r'''
.panel{margin:2vw;width:min(94vw,780px);border-radius:26px;padding:24px 28px}.top{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-bottom:14px}.title{font-size:clamp(32px,3.2vw,48px);font-weight:950;letter-spacing:-.03em}.sub{color:var(--muted);font-size:clamp(14px,1.2vw,19px);font-weight:760}.rows{display:flex;flex-direction:column;gap:7px}.row{display:grid;grid-template-columns:54px minmax(0,1fr) 112px;align-items:center;gap:10px;padding:11px 13px;border:1px solid var(--line);background:var(--soft);border-radius:14px}.row.top1{border-color:color-mix(in srgb,var(--gold) 55%,transparent)}.rank{font-size:clamp(20px,2vw,29px);font-weight:950}.name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:clamp(17px,1.55vw,24px);font-weight:820}.value{text-align:right;font-size:clamp(17px,1.5vw,23px);font-weight:920}.empty{text-align:center;padding:32px 0;color:var(--muted);font-size:20px;font-weight:760}.compact .row{padding:7px 10px}.compact .title{font-size:34px}.compact .panel{padding:18px 20px}
</style></head><body><div class="panel surface slide-up"><div class="top"><div class="title">TOP 10</div><div id="sub" class="sub"></div></div><div id="rows" class="rows"></div></div><script>
function esc(v){return String(v??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}let last='';async function tick(){try{const s=await(await fetch('/api/state?ts='+Date.now(),{cache:'no-store'})).json();document.body.classList.toggle('light',s.visual?.theme==='light');document.body.classList.toggle('no-motion',s.visual?.motion===false);document.body.classList.toggle('compact',s.visual?.compactRanking===true);const mode=s.rankingMode;document.querySelector('#sub').textContent=mode==='score'?'점수 기준':mode==='streak'?'최고 연속 정답 기준':'맞힌 개수 기준';const rows=s.ranking||[];const html=rows.length?rows.map(x=>'<div class="row '+(x.rank===1?'top1':'')+'"><div class="rank">'+x.rank+'</div><div class="name">'+esc(x.display)+'</div><div class="value">'+(mode==='score'?x.score.toLocaleString()+'점':mode==='streak'?x.streak+'연속':x.correct+'개')+'</div></div>').join(''):'<div class="empty">아직 순위가 없습니다</div>';if(html!==last){document.querySelector('#rows').innerHTML=html;last=html}}catch(e){}setTimeout(tick,220)}tick();
</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    engine: QuizEngine = None  # type: ignore

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/state":
            self._send(200, json.dumps(self.engine.public_state(), ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
        elif path in {"/", "/overlay/quiz"}:
            self._send(200, QUIZ_HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/overlay/ranking":
            self._send(200, RANK_HTML.encode("utf-8"), "text/html; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain; charset=utf-8")


class OverlayServer:
    def __init__(self, engine: QuizEngine, preferred_port: int = 8765) -> None:
        self.engine = engine
        self.port = self._find_port(preferred_port)
        Handler.engine = engine
        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True, name="overlay-http")

    @staticmethod
    def _find_port(preferred: int) -> int:
        for port in range(preferred, preferred + 10):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("127.0.0.1", port))
                    return port
                except OSError:
                    continue
        raise RuntimeError("방송 레이어용 빈 포트를 찾지 못했습니다.")

    @property
    def quiz_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/overlay/quiz"

    @property
    def ranking_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/overlay/ranking"

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        try:
            self.server.shutdown()
            self.server.server_close()
        except Exception:
            pass
