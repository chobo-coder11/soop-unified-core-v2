from __future__ import annotations

import json
import socket
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from quiz_engine_v5 import QuizEngineV5


BASE = r'''
:root{--accent:#5b7cff;--surface:rgba(15,18,26,.96);--panel:rgba(28,33,45,.96);--soft:rgba(255,255,255,.065);--line:rgba(255,255,255,.12);--text:#f7f8fb;--muted:#a2abba;--good:#42ca8a;--danger:#f05b6c;--gold:#f1c35b;--shadow:0 18px 46px rgba(0,0,0,.26)}
body.light{--surface:rgba(250,251,253,.98);--panel:rgba(255,255,255,.99);--soft:rgba(17,24,39,.052);--line:rgba(17,24,39,.11);--text:#141821;--muted:#667184;--good:#13875b;--danger:#ca3e50;--gold:#a46c00;--shadow:0 15px 36px rgba(25,35,52,.14)}
*{box-sizing:border-box}html,body{width:100%;height:100%;margin:0;background:transparent;overflow:hidden;font-family:"Segoe UI Variable","Segoe UI","Malgun Gothic",sans-serif;color:var(--text)}
body.style-minimal{--shadow:none}body.style-neon{--accent:#8b6cff;--surface:rgba(9,10,18,.95);--line:rgba(139,108,255,.28)}body.style-game{--accent:#ffb329;--surface:rgba(17,19,28,.97);--gold:#ffca50}
.shell{width:100%;height:100%;display:flex;align-items:center;justify-content:center;padding:3vw}.surface{background:var(--surface);border:1px solid var(--line);box-shadow:var(--shadow)}
.enter{animation:enter .32s cubic-bezier(.2,.78,.2,1) both}.pop{animation:pop .38s cubic-bezier(.16,.9,.24,1.15) both}.no-motion *{animation:none!important;transition:none!important}
@keyframes enter{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}@keyframes pop{from{opacity:.2;transform:scale(.94)}to{opacity:1;transform:scale(1)}}
.style-neon .surface{box-shadow:0 0 0 1px rgba(139,108,255,.1),0 18px 54px rgba(0,0,0,.35)}.style-minimal .surface{border-radius:18px!important;background:rgba(10,12,18,.90)}
'''

QUIZ = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>''' + BASE + r'''
.card{width:min(94vw,1500px);border-radius:30px;padding:30px 36px}.top{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:22px}.eyebrow{font-size:clamp(15px,1.15vw,22px);font-weight:850;letter-spacing:.08em;color:var(--muted)}.chips{display:flex;gap:8px}.chip{padding:8px 12px;border:1px solid var(--line);background:var(--soft);border-radius:999px;font-size:clamp(14px,1vw,19px);font-weight:850}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--good);margin-right:7px}.q{font-size:clamp(34px,3.65vw,67px);font-weight:900;line-height:1.18;letter-spacing:-.042em;word-break:keep-all}.choices{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:25px}.choice{display:flex;align-items:center;gap:14px;min-height:78px;padding:15px 18px;border:1px solid var(--line);background:var(--soft);border-radius:17px;font-size:clamp(21px,1.85vw,34px);font-weight:760}.choice.correct{border-color:rgba(66,202,138,.7);background:rgba(66,202,138,.13)}.n{display:grid;place-items:center;width:40px;height:40px;flex:0 0 40px;border-radius:12px;background:var(--panel);border:1px solid var(--line);font-size:.8em;font-weight:950}.foot{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;margin-top:23px}.instruction{font-size:clamp(20px,1.75vw,32px);font-weight:900}.hint{margin-top:5px;color:var(--muted);font-size:clamp(14px,1.05vw,20px);font-weight:720}.timer{font-size:clamp(36px,3.2vw,56px);font-weight:950;font-variant-numeric:tabular-nums}.bar{height:6px;margin-top:10px;border-radius:99px;background:var(--soft);overflow:hidden}.bar i{display:block;height:100%;background:var(--accent);transition:width .1s linear}.hero{text-align:center;padding:34px 8px}.hero .k{font-size:clamp(15px,1.15vw,21px);font-weight:850;color:var(--muted);letter-spacing:.09em}.hero .t{margin-top:8px;font-size:clamp(58px,6.8vw,116px);font-weight:970;letter-spacing:-.055em;line-height:1}.hero .s{margin-top:17px;font-size:clamp(19px,1.75vw,31px);font-weight:760;color:var(--muted)}.accent{color:var(--accent)}.answer{text-align:center;font-size:clamp(48px,5.8vw,96px);font-weight:970;letter-spacing:-.045em;margin:8px 0 18px}.fast{display:flex;justify-content:center;gap:9px;flex-wrap:wrap;margin-top:17px}.fast span{padding:8px 12px;border:1px solid var(--line);background:var(--soft);border-radius:12px;font-weight:780}.warn{position:absolute;left:2vw;bottom:2vw;max-width:min(74vw,1000px);padding:11px 15px;border-radius:12px;background:rgba(181,45,61,.97);color:white;font-size:15px;font-weight:800}.hidden{display:none}
@media(max-width:900px){.card{padding:22px}.choices{grid-template-columns:1fr}}
</style></head><body><div class="shell"><main class="card surface"><div id="content"></div></main></div><div id="warn" class="warn hidden"></div><script>
const C=document.querySelector('#content'),W=document.querySelector('#warn');let S=null,scene='',tm=0;const esc=v=>String(v??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function visual(s){document.body.classList.toggle('light',s.visual?.theme==='light');document.body.classList.toggle('no-motion',s.visual?.motion===false);for(const x of ['clean','game','neon','minimal'])document.body.classList.toggle('style-'+x,(s.visual?.style||'clean')===x);if(s.visual?.accent)document.documentElement.style.setProperty('--accent',s.visual.accent)}
function choices(q,correct=''){if(q.kind==='multiple')return '<div class="choices">'+q.choices.map((v,i)=>'<div class="choice '+(String(i+1)===String(correct)?'correct':'')+'"><span class="n">'+(i+1)+'</span><span>'+esc(v)+'</span></div>').join('')+'</div>';if(q.kind==='ox')return '<div class="choices"><div class="choice '+(correct==='O'?'correct':'')+'"><span class="n">O</span><span>맞다</span></div><div class="choice '+(correct==='X'?'correct':'')+'"><span class="n">X</span><span>아니다</span></div></div>';return ''}
function top(s){return '<div class="top"><div class="eyebrow">QUESTION '+(s.questionIndex+1)+' / '+s.questionCount+'</div><div class="chips"><span class="chip"><i class="dot"></i><b id="p">'+s.participants.toLocaleString()+'</b>명</span><span id="a" class="chip">답변 '+s.answered.toLocaleString()+'</span>'+(s.eliminated?'<span class="chip">생존 '+s.survivors.toLocaleString()+'</span>':'')+'</div></div>'}
function stop(){if(tm){clearInterval(tm);tm=0}}function timer(){stop();const r=()=>{if(!S||S.state!=='ANSWERING')return;const left=Math.max(0,Number(S.deadlineEpochMs||0)-Date.now()),el=document.querySelector('#timer'),bar=document.querySelector('#bar');if(el)el.textContent=(left/1000).toFixed(1)+'초';if(bar){const total=Math.max(1000,Number(S.question?.duration_sec||1)*1000);bar.style.width=Math.max(0,Math.min(100,left/total*100))+'%'}};r();tm=setInterval(r,100)}
function render(s){stop();scene=s.state+':'+s.questionIndex;const q=s.question;if(['DISCONNECTED','READY'].includes(s.state)){C.innerHTML='<div class="hero enter"><div class="k">SOOP LIVE QUIZ</div><div class="t">QUIZ</div><div class="s">진행자 프로그램에서 퀴즈를 시작해주세요</div></div>';return}if(s.state==='RECRUITING'){C.innerHTML='<div class="hero pop"><div class="k">NOW OPEN</div><div class="t">참가 모집</div><div class="s">채팅에 <b class="accent">!참여</b> · 현재 <b id="recruit" class="accent">'+s.participants.toLocaleString()+'</b>명</div></div>';return}if(s.state==='LOCKED'){C.innerHTML='<div class="hero enter"><div class="k">READY</div><div class="t">'+s.participants.toLocaleString()+'명 참가</div><div class="s">다음 문제를 준비하고 있습니다</div></div>';return}if(s.state==='QUESTION_VOID'){C.innerHTML='<div class="hero pop"><div class="k">VOID</div><div class="t">문제 무효</div><div class="s">이 문제의 점수는 반영되지 않습니다</div></div>';return}if(!q)return;
if(s.state==='QUESTION_SHOWN'){C.innerHTML=top(s)+'<div class="q enter">'+esc(q.prompt)+'</div>'+choices(q)+'<div class="foot"><div><div class="instruction">문제를 먼저 확인하세요</div><div class="hint">START 이후 입력만 정답으로 인정됩니다</div></div><span class="chip">답변 대기</span></div>';return}
if(s.state==='ANSWERING'){C.innerHTML=top(s)+'<div class="q">'+esc(q.prompt)+'</div>'+choices(q)+'<div class="foot"><div><div class="instruction"><b class="accent pop" style="display:inline-block;margin-right:12px">START</b>정답을 입력하세요</div><div class="hint">'+esc(s.answerHint||'')+'</div></div><div id="timer" class="timer"></div></div><div class="bar"><i id="bar"></i></div>';timer();return}
if(s.state==='QUESTION_CLOSED'){C.innerHTML=top(s)+'<div class="q">'+esc(q.prompt)+'</div>'+choices(q)+'<div class="hero pop" style="padding:24px 8px 8px"><div class="k">ANSWER CLOSED</div><div class="t" style="font-size:clamp(50px,5.5vw,90px)">마감</div><div class="s"><b class="accent">'+s.answered.toLocaleString()+'</b>명 답변 · 정답 공개 대기</div></div>';return}
if(s.state==='ANSWER_REVEALED'){let ans=esc(q.answer);if(q.kind==='multiple'){const i=Number(q.answer)-1;ans=esc(q.answer)+'. '+esc(q.choices[i]||'')}if(q.kind==='number'&&q.number_mode==='closest')ans='기준값 '+esc(q.answer);const fast=(s.visual?.showFastest===false?[]:s.firstCorrect.slice(0,3)).map(x=>'<span>'+x.rank+'위 '+esc(x.display)+' · '+(x.elapsedMs/1000).toFixed(3)+'초</span>').join('');C.innerHTML=top(s)+'<div class="eyebrow" style="text-align:center">정답</div><div class="answer pop">'+ans+'</div>'+choices(q,String(q.answer))+'<div class="foot"><div><div class="instruction">정답자 <b class="accent">'+s.correct.toLocaleString()+'</b>명</div><div class="hint">정답률 '+(s.answered?((s.correct/s.answered)*100).toFixed(1):'0.0')+'%'+(q.score_multiplier&&q.score_multiplier!==1?' · '+q.score_multiplier+'배 배점':'')+'</div></div></div><div class="fast">'+fast+'</div>';return}
if(s.state==='FINISHED'){C.innerHTML='<div class="hero pop"><div class="k">FINAL</div><div class="t">QUIZ END</div><div class="s">최종 순위를 확인해주세요</div></div>'}}
function patch(s){const k=s.state+':'+s.questionIndex;if(k!==scene)return render(s);for(const [id,v] of [['p',s.participants],['recruit',s.participants]]){const e=document.getElementById(id);if(e)e.textContent=Number(v||0).toLocaleString()}const a=document.getElementById('a');if(a)a.textContent='답변 '+s.answered.toLocaleString()}
function apply(s){S=s;visual(s);W.classList.toggle('hidden',!s.integrityWarning);W.textContent=s.integrityWarning||'';patch(s)}async function init(){try{apply(await(await fetch('/api/state',{cache:'no-store'})).json())}catch{}}function events(){if(!window.EventSource){setInterval(init,2000);return}const e=new EventSource('/api/events');e.onmessage=x=>{try{apply(JSON.parse(x.data))}catch{}}}init().then(events);
</script></body></html>'''

RANK = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>''' + BASE + r'''
.panel{width:min(94vw,780px);margin:2vw;border-radius:25px;padding:22px 24px}.head{display:flex;align-items:flex-end;justify-content:space-between;margin-bottom:13px}.title{font-size:clamp(30px,3vw,47px);font-weight:970;letter-spacing:-.045em}.sub{font-size:clamp(13px,1vw,18px);font-weight:760;color:var(--muted)}.rows{display:flex;flex-direction:column;gap:7px}.row{display:grid;grid-template-columns:46px minmax(0,1fr) 120px;gap:10px;align-items:center;padding:10px 12px;border:1px solid var(--line);background:var(--soft);border-radius:13px;transition:transform .25s ease,opacity .25s ease}.row.out{opacity:.55}.rank{font-size:clamp(19px,1.8vw,27px);font-weight:970}.name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:clamp(16px,1.45vw,22px);font-weight:820}.value{text-align:right;font-size:clamp(15px,1.3vw,21px);font-weight:920}.empty{text-align:center;padding:26px;color:var(--muted);font-weight:760}
</style></head><body><main class="panel surface enter"><div class="head"><div class="title">TOP <span id="n">10</span></div><div id="sub" class="sub"></div></div><div id="rows" class="rows"></div></main><script>
const R=document.querySelector('#rows'),SUB=document.querySelector('#sub'),N=document.querySelector('#n');let last='';const esc=v=>String(v??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));function vis(s){document.body.classList.toggle('light',s.visual?.theme==='light');document.body.classList.toggle('no-motion',s.visual?.motion===false);for(const x of ['clean','game','neon','minimal'])document.body.classList.toggle('style-'+x,(s.visual?.style||'clean')===x);if(s.visual?.accent)document.documentElement.style.setProperty('--accent',s.visual.accent)}function apply(s){vis(s);const qs=new URLSearchParams(location.search),lim=Math.max(1,Math.min(10,Number(qs.get('limit')||10))),rows=(s.ranking||[]).slice(0,lim);N.textContent=lim;SUB.textContent=s.rankingMode==='score'?'점수 기준':s.rankingMode==='streak'?'연속 정답 기준':'정답 개수 기준';const sig=JSON.stringify(rows);if(sig===last)return;last=sig;R.innerHTML=rows.length?rows.map(x=>'<div class="row '+(x.eliminated?'out':'')+'"><div class="rank">'+x.rank+'</div><div class="name">'+esc(x.display)+(x.eliminated?' · 탈락':'')+'</div><div class="value">'+(s.rankingMode==='score'?x.score.toLocaleString()+'점':s.rankingMode==='streak'?x.streak+'연속':x.correct+'개')+'</div></div>').join(''):'<div class="empty">순위 데이터가 아직 없습니다.</div>'}async function init(){try{apply(await(await fetch('/api/state',{cache:'no-store'})).json())}catch{}}function ev(){const e=new EventSource('/api/events');e.onmessage=x=>{try{apply(JSON.parse(x.data))}catch{}}}init().then(ev);
</script></body></html>'''

STATUS = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>''' + BASE + r'''
body{display:flex;align-items:center;justify-content:center}.pill{display:flex;gap:12px;align-items:center;padding:11px 16px;border-radius:999px;font-size:20px;font-weight:850}.small{font-size:15px;color:var(--muted)}</style></head><body><div class="pill surface"><span id="stage">대기</span><span id="info" class="small"></span></div><script>const a=document.querySelector('#stage'),b=document.querySelector('#info');function f(s){a.textContent=({RECRUITING:'참가 모집',QUESTION_SHOWN:'문제 공개',ANSWERING:'정답 입력',QUESTION_CLOSED:'답변 마감',ANSWER_REVEALED:'정답 공개',QUESTION_VOID:'문제 무효',FINISHED:'퀴즈 종료'})[s.state]||'대기';b.textContent='참가 '+s.participants.toLocaleString()+' · 답변 '+s.answered.toLocaleString()}async function i(){try{f(await(await fetch('/api/state')).json())}catch{}}i().then(()=>{const e=new EventSource('/api/events');e.onmessage=x=>{try{f(JSON.parse(x.data))}catch{}}})</script></body></html>'''


class HandlerV5(BaseHTTPRequestHandler):
    engine: QuizEngineV5
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args) -> None:
        return

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
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
                version = self.engine.wait_for_update(last, timeout=10.0)
                if version == last:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue
                time.sleep(0.035)
                payload = json.dumps(self.engine.public_state(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                self.wfile.write(b"data: " + payload + b"\n\n")
                self.wfile.flush()
                last = self.engine.state_version
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/state":
            self._send(200, json.dumps(self.engine.public_state(), ensure_ascii=False, separators=(",", ":")).encode(), "application/json; charset=utf-8")
        elif path == "/api/events":
            self._events()
        elif path == "/api/health":
            self._send(200, b'{"ok":true,"version":"0.5.0"}', "application/json")
        elif path in {"/", "/overlay/quiz"}:
            self._send(200, QUIZ.encode("utf-8"), "text/html; charset=utf-8")
        elif path in {"/overlay/rank", "/overlay/top10", "/overlay/top3"}:
            html = RANK
            self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/overlay/status":
            self._send(200, STATUS.encode("utf-8"), "text/html; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain")


class OverlayServerV5:
    def __init__(self, engine: QuizEngineV5, preferred_port: int = 8765) -> None:
        self.engine = engine
        self.port = self._find_port(preferred_port)
        HandlerV5.engine = engine
        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), HandlerV5)
        self.server.daemon_threads = True
        self.thread: threading.Thread | None = None

    @staticmethod
    def _find_port(preferred: int) -> int:
        for port in range(preferred, preferred + 30):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                try:
                    sock.bind(("127.0.0.1", port))
                except OSError:
                    continue
                return port
        raise RuntimeError("방송 레이어용 빈 포트를 찾지 못했습니다.")

    @property
    def quiz_url(self) -> str: return f"http://127.0.0.1:{self.port}/overlay/quiz"
    @property
    def rank_url(self) -> str: return f"http://127.0.0.1:{self.port}/overlay/top10"
    @property
    def top3_url(self) -> str: return f"http://127.0.0.1:{self.port}/overlay/top3?limit=3"
    @property
    def status_url(self) -> str: return f"http://127.0.0.1:{self.port}/overlay/status"
    @property
    def health_url(self) -> str: return f"http://127.0.0.1:{self.port}/api/health"

    def start(self) -> None:
        if self.thread and self.thread.is_alive(): return
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.25}, daemon=True, name="overlay-http-v5")
        self.thread.start()

    def is_healthy(self) -> bool:
        return bool(self.thread and self.thread.is_alive())

    def stop(self) -> None:
        try:
            self.server.shutdown(); self.server.server_close()
        except Exception:
            pass
