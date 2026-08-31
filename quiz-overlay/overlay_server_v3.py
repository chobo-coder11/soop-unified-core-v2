from __future__ import annotations

import json
import socket
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from quiz_engine_v3 import QuizEngineV3


BASE_CSS = r'''
:root{--surface:rgba(15,18,26,.96);--panel:rgba(28,33,45,.96);--soft:rgba(255,255,255,.065);--line:rgba(255,255,255,.11);--text:#f6f8fc;--muted:#9aa5b7;--accent:#5b8cff;--good:#46c98b;--danger:#ef6572;--gold:#f2c15b;--shadow:0 16px 42px rgba(0,0,0,.24)}
body.light{--surface:rgba(249,250,252,.97);--panel:rgba(255,255,255,.98);--soft:rgba(17,24,39,.05);--line:rgba(17,24,39,.10);--text:#171b24;--muted:#687386;--accent:#356df3;--good:#13875b;--danger:#d04452;--gold:#a86f00;--shadow:0 14px 34px rgba(26,36,54,.14)}
*{box-sizing:border-box}html,body{width:100%;height:100%;margin:0;background:transparent;overflow:hidden;font-family:"Segoe UI Variable","Segoe UI","Malgun Gothic",sans-serif;color:var(--text)}
.shell{width:100%;height:100%;display:flex;align-items:center;justify-content:center;padding:3vw}.surface{background:var(--surface);border:1px solid var(--line);box-shadow:var(--shadow)}
.enter{animation:enter .34s cubic-bezier(.2,.75,.2,1) both}.punch{animation:punch .42s cubic-bezier(.18,.88,.25,1.18) both}.no-motion *{animation:none!important;transition:none!important}
@keyframes enter{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}@keyframes punch{0%{opacity:.15;transform:scale(.9)}100%{opacity:1;transform:scale(1)}}
'''

QUIZ_HTML = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>''' + BASE_CSS + r'''
.card{width:min(93vw,1460px);border-radius:28px;padding:30px 36px}.top{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:22px}.qmeta{font-size:clamp(17px,1.3vw,24px);font-weight:800;color:var(--muted)}.chips{display:flex;gap:8px;align-items:center}.chip{padding:8px 12px;border:1px solid var(--line);background:var(--soft);border-radius:999px;font-size:clamp(15px,1.08vw,20px);font-weight:800}.live-dot{display:inline-block;width:8px;height:8px;margin-right:7px;border-radius:50%;background:var(--good)}
.question{font-size:clamp(34px,3.65vw,66px);font-weight:880;line-height:1.2;letter-spacing:-.035em;word-break:keep-all}.choices{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:24px}.choice{display:flex;align-items:center;gap:14px;min-height:76px;padding:15px 18px;border:1px solid var(--line);background:var(--soft);border-radius:16px;font-size:clamp(22px,1.9vw,34px);font-weight:760}.choice.correct{border-color:rgba(70,201,139,.65);background:rgba(70,201,139,.12)}.num{display:grid;place-items:center;width:38px;height:38px;flex:0 0 38px;border-radius:11px;background:var(--panel);border:1px solid var(--line);font-size:.8em;font-weight:900}
.foot{display:flex;align-items:flex-end;justify-content:space-between;gap:22px;margin-top:23px}.instruction{font-size:clamp(21px,1.8vw,33px);font-weight:900}.hint{margin-top:5px;color:var(--muted);font-size:clamp(15px,1.1vw,20px);font-weight:700}.timer{font-size:clamp(34px,3vw,52px);font-weight:900;font-variant-numeric:tabular-nums;text-align:right}.timer small{font-size:.42em;color:var(--muted);margin-left:4px}.bar{height:6px;margin-top:11px;border-radius:999px;background:var(--soft);overflow:hidden}.bar>i{display:block;height:100%;width:100%;border-radius:inherit;background:var(--accent);transition:width .12s linear}
.hero{text-align:center;padding:35px 10px}.hero-kicker{font-size:clamp(16px,1.2vw,21px);font-weight:800;color:var(--muted);letter-spacing:.08em}.hero-title{margin-top:8px;font-size:clamp(60px,7vw,118px);font-weight:950;letter-spacing:-.055em;line-height:.98}.hero-sub{margin-top:18px;font-size:clamp(20px,1.8vw,32px);font-weight:760;color:var(--muted)}.accent{color:var(--accent)}
.answer-label{text-align:center;color:var(--muted);font-size:clamp(18px,1.5vw,27px);font-weight:800}.answer{text-align:center;margin:8px 0 18px;font-size:clamp(48px,5.8vw,96px);font-weight:950;letter-spacing:-.04em}.fast{display:flex;justify-content:center;gap:9px;flex-wrap:wrap;margin-top:18px}.fast>span{padding:8px 12px;border-radius:12px;background:var(--soft);border:1px solid var(--line);font-size:clamp(14px,1vw,19px);font-weight:780}
.warn{position:absolute;left:2vw;bottom:2vw;max-width:min(72vw,960px);padding:11px 15px;border-radius:12px;background:rgba(184,50,65,.96);color:#fff;font-size:15px;font-weight:780;box-shadow:0 12px 28px rgba(0,0,0,.22)}.hidden{display:none}
@media(max-width:900px){.card{padding:22px}.choices{grid-template-columns:1fr}.foot{align-items:flex-end}.choice{min-height:64px}}
</style></head><body><div class="shell"><main id="card" class="card surface"><div id="content"></div></main></div><div id="warn" class="warn hidden"></div><script>
const content=document.querySelector('#content'),warn=document.querySelector('#warn');let state=null,scene='',timerHandle=0;
const esc=v=>String(v??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function applyVisual(s){document.body.classList.toggle('light',s.visual?.theme==='light');document.body.classList.toggle('no-motion',s.visual?.motion===false)}
function choiceHtml(q,correct=''){if(q.kind==='multiple')return '<div class="choices">'+q.choices.map((v,i)=>'<div class="choice '+(String(i+1)===String(correct)?'correct':'')+'"><span class="num">'+(i+1)+'</span><span>'+esc(v)+'</span></div>').join('')+'</div>';if(q.kind==='ox')return '<div class="choices"><div class="choice '+(correct==='O'?'correct':'')+'"><span class="num">O</span><span>맞다</span></div><div class="choice '+(correct==='X'?'correct':'')+'"><span class="num">X</span><span>아니다</span></div></div>';return ''}
function topHtml(s){return '<div class="top"><div class="qmeta">QUESTION '+(s.questionIndex+1)+' <span style="opacity:.45">/ '+s.questionCount+'</span></div><div class="chips"><span class="chip"><i class="live-dot"></i><span id="part">'+s.participants.toLocaleString()+'</span>명</span><span id="answeredChip" class="chip">답변 '+s.answered.toLocaleString()+'</span></div></div>'}
function stopTimer(){if(timerHandle){clearInterval(timerHandle);timerHandle=0}}
function startTimer(){stopTimer();const render=()=>{if(!state||state.state!=='ANSWERING')return;const end=Number(state.deadlineEpochMs||0),left=Math.max(0,end-Date.now()),sec=(left/1000).toFixed(1),el=document.querySelector('#timer'),bar=document.querySelector('#timerBar');if(el)el.innerHTML=sec+'<small>초</small>';if(bar){const total=Math.max(1000,Number(state.question?.duration_sec||1)*1000);bar.style.width=Math.max(0,Math.min(100,left/total*100))+'%'}};render();timerHandle=setInterval(render,100)}
function renderScene(s){stopTimer();const key=s.state+':'+s.questionIndex;scene=key;const q=s.question;
if(s.state==='DISCONNECTED'||s.state==='READY'){content.innerHTML='<div class="hero enter"><div class="hero-kicker">SOOP LIVE INTERACTION</div><div class="hero-title">QUIZ</div><div class="hero-sub">진행자 프로그램에서 퀴즈를 시작해주세요</div></div>';return}
if(s.state==='RECRUITING'){content.innerHTML='<div class="hero punch"><div class="hero-kicker">NOW OPEN</div><div class="hero-title">참가 모집</div><div class="hero-sub">채팅에 <b class="accent">!참여</b> 입력 · 현재 <b id="recruitCount" class="accent">'+s.participants.toLocaleString()+'</b>명</div></div>';return}
if(s.state==='LOCKED'){content.innerHTML='<div class="hero enter"><div class="hero-kicker">READY</div><div class="hero-title">'+s.participants.toLocaleString()+'명 참가</div><div class="hero-sub">진행자가 다음 문제를 준비하고 있습니다</div></div>';return}
if(!q){content.innerHTML='<div class="hero"><div class="hero-title">QUIZ</div></div>';return}
if(s.state==='QUESTION_SHOWN'){content.innerHTML=topHtml(s)+'<div class="question enter">'+esc(q.prompt)+'</div>'+choiceHtml(q)+'<div class="foot"><div><div class="instruction">문제를 먼저 확인하세요</div><div class="hint">START 이후 채팅만 정답으로 인정됩니다</div></div><span class="chip">답변 대기</span></div>';return}
if(s.state==='ANSWERING'){content.innerHTML=topHtml(s)+'<div class="question">'+esc(q.prompt)+'</div>'+choiceHtml(q)+'<div class="foot"><div><div class="instruction"><b class="accent punch" style="display:inline-block;margin-right:12px">START</b>정답을 입력하세요</div><div class="hint">'+esc(s.answerHint||'')+'</div></div><div id="timer" class="timer"></div></div><div class="bar"><i id="timerBar"></i></div>';startTimer();return}
if(s.state==='QUESTION_CLOSED'){content.innerHTML=topHtml(s)+'<div class="question">'+esc(q.prompt)+'</div>'+choiceHtml(q)+'<div class="hero punch" style="padding:24px 8px 8px"><div class="hero-kicker">ANSWER CLOSED</div><div class="hero-title" style="font-size:clamp(52px,5.5vw,92px)">마감</div><div class="hero-sub"><b class="accent">'+s.answered.toLocaleString()+'</b>명 답변 · 정답 공개 대기</div></div>';return}
if(s.state==='ANSWER_REVEALED'){let ans=esc(q.answer);if(q.kind==='multiple'){const idx=Number(q.answer)-1;ans=esc(q.answer)+'. '+esc(q.choices[idx]||'')}const fast=(s.visual?.showFastest===false?[]:s.firstCorrect.slice(0,3)).map(x=>'<span>'+x.rank+'위 '+esc(x.display)+' · '+(x.elapsedMs/1000).toFixed(3)+'초</span>').join('');content.innerHTML=topHtml(s)+'<div class="answer-label">정답</div><div class="answer punch">'+ans+'</div>'+choiceHtml(q,String(q.answer))+'<div class="foot"><div><div class="instruction">정답자 <b class="accent">'+s.correct.toLocaleString()+'</b>명</div><div class="hint">정답률 '+(s.answered?((s.correct/s.answered)*100).toFixed(1):'0.0')+'%</div></div></div><div class="fast">'+fast+'</div>';return}
if(s.state==='FINISHED'){content.innerHTML='<div class="hero punch"><div class="hero-kicker">FINAL</div><div class="hero-title">QUIZ END</div><div class="hero-sub">최종 TOP 10을 확인해주세요</div></div>'}}
function patch(s){const key=s.state+':'+s.questionIndex;if(key!==scene){renderScene(s);return}const p=document.querySelector('#part'),r=document.querySelector('#recruitCount'),a=document.querySelector('#answeredChip');if(p)p.textContent=s.participants.toLocaleString();if(r)r.textContent=s.participants.toLocaleString();if(a)a.textContent='답변 '+s.answered.toLocaleString()}
function apply(s){state=s;applyVisual(s);warn.classList.toggle('hidden',!s.integrityWarning);warn.textContent=s.integrityWarning||'';patch(s)}
async function initial(){try{apply(await(await fetch('/api/state',{cache:'no-store'})).json())}catch(e){}}
function connectEvents(){if(!window.EventSource){setInterval(initial,2000);return}const es=new EventSource('/api/events');es.onmessage=e=>{try{apply(JSON.parse(e.data))}catch(_){}};es.onerror=()=>{}}
initial().then(connectEvents);
</script></body></html>'''

RANK_HTML = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>''' + BASE_CSS + r'''
.panel{width:min(94vw,760px);margin:2vw;border-radius:24px;padding:22px 24px}.head{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-bottom:13px}.title{font-size:clamp(30px,3vw,46px);font-weight:950;letter-spacing:-.045em}.sub{font-size:clamp(13px,1vw,18px);font-weight:760;color:var(--muted)}.rows{display:flex;flex-direction:column;gap:7px}.row{display:grid;grid-template-columns:46px minmax(0,1fr) 110px;gap:10px;align-items:center;padding:10px 12px;border-radius:13px;border:1px solid var(--line);background:var(--soft)}.row.first{border-color:rgba(242,193,91,.52)}.rank{font-size:clamp(19px,1.8vw,27px);font-weight:950}.name{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:clamp(16px,1.45vw,22px);font-weight:800}.value{text-align:right;font-size:clamp(16px,1.4vw,22px);font-weight:900}.empty{text-align:center;padding:26px;color:var(--muted);font-size:18px;font-weight:760}.compact .row{padding:7px 10px}.compact .panel{padding:16px 18px}
</style></head><body><main class="panel surface enter"><div class="head"><div class="title">TOP 10</div><div id="sub" class="sub"></div></div><div id="rows" class="rows"></div></main><script>
const rowsEl=document.querySelector('#rows'),sub=document.querySelector('#sub');let last='';const esc=v=>String(v??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function apply(s){document.body.classList.toggle('light',s.visual?.theme==='light');document.body.classList.toggle('no-motion',s.visual?.motion===false);document.body.classList.toggle('compact',s.visual?.compactRanking===true);const mode=s.rankingMode;sub.textContent=mode==='score'?'점수 기준':mode==='streak'?'최고 연속 정답':'맞힌 개수';const key=JSON.stringify((s.ranking||[]).map(x=>[x.userId,x.correct,x.score,x.streak,x.rank]))+mode;if(key===last)return;last=key;const rows=s.ranking||[];rowsEl.innerHTML=rows.length?rows.map(x=>'<div class="row '+(x.rank===1?'first':'')+'"><div class="rank">'+x.rank+'</div><div class="name">'+esc(x.display)+'</div><div class="value">'+(mode==='score'?x.score.toLocaleString()+'점':mode==='streak'?x.streak+'연속':x.correct+'개')+'</div></div>').join(''):'<div class="empty">정답 공개 후 순위가 표시됩니다</div>'}
async function initial(){try{apply(await(await fetch('/api/state',{cache:'no-store'})).json())}catch(e){}}function connect(){if(!window.EventSource){setInterval(initial,2500);return}const es=new EventSource('/api/events');es.onmessage=e=>{try{apply(JSON.parse(e.data))}catch(_){}}}initial().then(connect);
</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    engine: QuizEngineV3
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        return

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _events(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        last = 0
        try:
            while True:
                version = self.engine.wait_for_update(last, timeout=9.0)
                if version == last:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue
                time.sleep(0.045)  # coalesce chat bursts into one browser update
                payload = json.dumps(self.engine.public_state(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                self.wfile.write(b"data: " + payload + b"\n\n")
                self.wfile.flush()
                last = self.engine.state_version
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/state":
            body = json.dumps(self.engine.public_state(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")
        elif path == "/api/events":
            self._events()
        elif path in {"/", "/overlay/quiz"}:
            self._send(200, QUIZ_HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/overlay/rank":
            self._send(200, RANK_HTML.encode("utf-8"), "text/html; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain; charset=utf-8")


class OverlayServerV3:
    def __init__(self, engine: QuizEngineV3, preferred_port: int = 8765) -> None:
        self.engine = engine
        self.port = self._find_port(preferred_port)
        Handler.engine = engine
        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self.server.daemon_threads = True
        self.thread: threading.Thread | None = None

    @staticmethod
    def _find_port(preferred: int) -> int:
        for port in range(preferred, preferred + 20):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                try:
                    sock.bind(("127.0.0.1", port))
                except OSError:
                    continue
                return port
        raise RuntimeError("레이어 서버용 빈 포트를 찾지 못했습니다.")

    @property
    def quiz_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/overlay/quiz"

    @property
    def rank_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/overlay/rank"

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.25}, daemon=True, name="overlay-http-v3")
        self.thread.start()

    def stop(self) -> None:
        try:
            self.server.shutdown()
            self.server.server_close()
        except Exception:
            pass
