from __future__ import annotations

import json
import socket
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Import v7 once so the existing ranking/status overlays keep their proven polish.
import overlay_server_v5 as legacy
import overlay_server_v7  # noqa: F401
from quiz_engine_v9 import QuizEngineV9, UI_VERSION


QUIZ = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
:root{--accent:#5b7cff;--surface:rgba(15,18,26,.965);--panel:rgba(28,33,45,.97);--soft:rgba(255,255,255,.065);--line:rgba(255,255,255,.12);--text:#f7f8fb;--muted:#a2abba;--good:#42ca8a;--danger:#f05b6c;--warning:#f1b85b;--shadow:0 18px 46px rgba(0,0,0,.26)}
body.light{--surface:rgba(250,251,253,.985);--panel:rgba(255,255,255,.995);--soft:rgba(17,24,39,.052);--line:rgba(17,24,39,.11);--text:#141821;--muted:#667184;--good:#13875b;--danger:#ca3e50;--warning:#a46c00;--shadow:0 15px 36px rgba(25,35,52,.14)}
*{box-sizing:border-box}html,body{width:100%;height:100%;margin:0;background:transparent;overflow:hidden;font-family:"Malgun Gothic","Segoe UI Variable","Segoe UI",sans-serif;color:var(--text)}
body.style-neon{--accent:#8b6cff;--surface:rgba(9,10,18,.96);--line:rgba(139,108,255,.28)}body.style-game{--accent:#ffb329;--surface:rgba(17,19,28,.975)}body.style-minimal{--shadow:none}
.shell{width:100%;height:100%;display:flex;align-items:center;justify-content:center;padding:clamp(8px,1.8vh,20px) clamp(10px,2vw,36px)}
.card{width:min(96vw,1580px);max-height:calc(100vh - 16px);overflow:hidden;border-radius:28px;padding:clamp(20px,2.2vh,32px) clamp(22px,2.4vw,42px);background:var(--surface);border:1px solid var(--line);box-shadow:var(--shadow)}
#content{min-width:0}.top{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:clamp(12px,1.6vh,20px)}
.eyebrow{font-size:clamp(14px,1.05vw,20px);font-weight:900;letter-spacing:.06em;color:var(--muted)}.chips{display:flex;gap:7px;flex-wrap:wrap;justify-content:flex-end}.chip{padding:7px 11px;border:1px solid var(--line);background:var(--soft);border-radius:999px;font-size:clamp(13px,.95vw,18px);font-weight:850;white-space:nowrap}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--good);margin-right:7px}
.q{font-size:clamp(32px,3.55vw,68px);font-weight:900;line-height:1.16;letter-spacing:-.045em;word-break:keep-all;overflow-wrap:anywhere}.choices{display:grid;grid-template-columns:1fr 1fr;gap:clamp(9px,1.2vh,14px) clamp(10px,1vw,16px);margin-top:clamp(15px,2vh,26px)}
.choice{display:flex;align-items:center;gap:13px;min-height:clamp(62px,8vh,88px);padding:clamp(10px,1.3vh,16px) clamp(13px,1.2vw,19px);border:1px solid var(--line);background:var(--soft);border-radius:17px;font-size:clamp(20px,1.75vw,34px);font-weight:780;line-height:1.18;min-width:0}.choice>span:last-child{min-width:0;overflow-wrap:anywhere}.choice.correct{border-color:rgba(66,202,138,.78);background:rgba(66,202,138,.14)}
.n{display:grid;place-items:center;width:40px;height:40px;flex:0 0 40px;border-radius:12px;background:var(--panel);border:1px solid var(--line);font-size:.78em;font-weight:950}.choice.correct .n{background:var(--good);border-color:var(--good);color:white}
.foot{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;margin-top:clamp(15px,2vh,24px);min-width:0}.instruction{font-size:clamp(19px,1.6vw,30px);font-weight:900;line-height:1.16}.hint{margin-top:5px;color:var(--muted);font-size:clamp(13px,1vw,19px);font-weight:720}.timer{font-size:clamp(34px,3vw,54px);font-weight:950;font-variant-numeric:tabular-nums;white-space:nowrap}.bar{height:7px;margin-top:10px;border-radius:99px;background:var(--soft);overflow:hidden}.bar i{display:block;height:100%;background:var(--accent);transition:width .1s linear}
.hero{text-align:center;padding:clamp(28px,4vh,52px) 8px}.hero .k{font-size:clamp(14px,1.1vw,21px);font-weight:850;color:var(--muted);letter-spacing:.08em}.hero .t{margin-top:8px;font-size:clamp(52px,6.3vw,108px);font-weight:970;letter-spacing:-.055em;line-height:1}.hero .s{margin-top:14px;font-size:clamp(18px,1.6vw,30px);font-weight:760;color:var(--muted)}
.answer-banner{display:flex;align-items:center;justify-content:center;gap:12px;margin-top:clamp(14px,1.7vh,22px);padding:clamp(12px,1.5vh,18px) 18px;border:1px solid rgba(66,202,138,.56);border-radius:17px;background:rgba(66,202,138,.11);font-size:clamp(24px,2.4vw,44px);font-weight:950;text-align:center;line-height:1.12}.answer-label{font-size:.48em;letter-spacing:.08em;color:var(--good);white-space:nowrap}.fast{display:flex;justify-content:flex-start;gap:7px;flex-wrap:wrap;margin-top:10px}.fast span{padding:7px 10px;border:1px solid var(--line);background:var(--soft);border-radius:11px;font-size:clamp(12px,.9vw,17px);font-weight:780}
.accent{color:var(--accent)}.good{color:var(--good)}.warn{position:absolute;left:2vw;bottom:2vw;max-width:min(78vw,1050px);padding:11px 15px;border-radius:12px;background:rgba(181,45,61,.97);color:white;font-size:15px;font-weight:800}.net{position:absolute;right:1.4vw;bottom:1.4vw;padding:8px 11px;border-radius:10px;background:rgba(30,34,44,.94);border:1px solid var(--line);color:var(--muted);font-size:12px;font-weight:800}.hidden{display:none}
.enter{animation:enter .28s cubic-bezier(.2,.78,.2,1) both}.pop{animation:pop .34s cubic-bezier(.16,.9,.24,1.1) both}.choices .choice{animation:choiceIn .26s ease both}.choices .choice:nth-child(2){animation-delay:.03s}.choices .choice:nth-child(3){animation-delay:.06s}.choices .choice:nth-child(4){animation-delay:.09s}.choices .choice:nth-child(5){animation-delay:.12s}.choices .choice:nth-child(6){animation-delay:.15s}.no-motion *{animation:none!important;transition:none!important}
@keyframes enter{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}@keyframes pop{from{opacity:.25;transform:scale(.95)}to{opacity:1;transform:scale(1)}}@keyframes choiceIn{from{opacity:0;transform:translateX(10px)}to{opacity:1;transform:translateX(0)}}
body.style-clean .card{border-radius:28px}body.style-game .card{border-radius:34px}body.style-game .top{padding-bottom:12px;border-bottom:2px solid rgba(255,202,80,.24)}body.style-game .q{text-align:center}body.style-game .choices{max-width:1400px;margin-left:auto;margin-right:auto}body.style-neon .choice{border-left-width:4px}body.style-minimal .card{border-radius:16px;background:rgba(10,12,18,.91);padding-left:28px;padding-right:28px}
/* Automatic height fitting. These classes are applied from JS after real layout measurement. */
.card.fit-1{padding-top:18px;padding-bottom:18px}.fit-1 .top{margin-bottom:10px}.fit-1 .q{font-size:clamp(28px,3vw,56px)}.fit-1 .choices{margin-top:13px;gap:8px 11px}.fit-1 .choice{min-height:56px;padding:9px 13px;font-size:clamp(18px,1.55vw,29px)}.fit-1 .foot{margin-top:12px}.fit-1 .answer-banner{margin-top:11px;padding:10px 14px}.fit-1 .fast{margin-top:7px}
.card.fit-2{padding:14px 22px}.fit-2 .top{margin-bottom:7px}.fit-2 .eyebrow{font-size:13px}.fit-2 .chip{padding:5px 8px;font-size:12px}.fit-2 .q{font-size:clamp(24px,2.6vw,47px);line-height:1.1}.fit-2 .choices{margin-top:10px;gap:7px 10px}.fit-2 .choice{min-height:48px;padding:7px 11px;font-size:clamp(16px,1.35vw,25px)}.fit-2 .n{width:34px;height:34px;flex-basis:34px}.fit-2 .foot{margin-top:9px}.fit-2 .instruction{font-size:clamp(16px,1.35vw,24px)}.fit-2 .hint{font-size:12px}.fit-2 .timer{font-size:clamp(28px,2.5vw,44px)}.fit-2 .answer-banner{margin-top:8px;padding:8px 12px;font-size:clamp(21px,2vw,36px)}.fit-2 .fast span{padding:5px 7px;font-size:11px}
.card.fit-3{padding:11px 18px}.fit-3 .top{margin-bottom:5px}.fit-3 .q{font-size:clamp(21px,2.2vw,40px);line-height:1.08}.fit-3 .choices{margin-top:7px;gap:5px 8px}.fit-3 .choice{min-height:42px;padding:6px 9px;font-size:clamp(15px,1.2vw,22px);border-radius:12px}.fit-3 .n{width:30px;height:30px;flex-basis:30px;border-radius:9px}.fit-3 .foot{margin-top:7px}.fit-3 .instruction{font-size:clamp(15px,1.2vw,21px)}.fit-3 .hint{font-size:11px}.fit-3 .timer{font-size:34px}.fit-3 .bar{height:5px;margin-top:6px}.fit-3 .answer-banner{margin-top:6px;padding:7px 10px;font-size:clamp(19px,1.8vw,31px)}.fit-3 .fast{display:none}
.card.fit-4{padding:8px 14px}.fit-4 .top{margin-bottom:4px}.fit-4 .chips{gap:4px}.fit-4 .q{font-size:clamp(18px,1.9vw,34px);line-height:1.05}.fit-4 .choices{margin-top:5px;gap:4px 6px}.fit-4 .choice{min-height:36px;padding:5px 7px;font-size:clamp(13px,1.05vw,19px)}.fit-4 .n{width:26px;height:26px;flex-basis:26px}.fit-4 .foot{margin-top:5px}.fit-4 .instruction{font-size:14px}.fit-4 .hint{font-size:10px}.fit-4 .answer-banner{font-size:18px;margin-top:5px;padding:5px 8px}.fit-4 .fast{display:none}
@media(max-width:850px){.shell{align-items:flex-start}.card{width:98vw}.choices{grid-template-columns:1fr}.q{font-size:clamp(26px,5.2vw,48px)}.choice{font-size:clamp(18px,3.6vw,28px);min-height:54px}.chips{max-width:55%}.foot{align-items:flex-start}.timer{font-size:34px}}
</style></head><body><div class="shell"><main id="card" class="card"><div id="content"></div></main></div><div id="warn" class="warn hidden"></div><div id="net" class="net hidden">레이어 연결 재시도 중</div><script>
const C=document.querySelector('#content'),CARD=document.querySelector('#card'),W=document.querySelector('#warn'),NET=document.querySelector('#net');let S=null,scene='',tm=0,es=null;const esc=v=>String(v??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function visual(s){document.body.classList.toggle('light',s.visual?.theme==='light');document.body.classList.toggle('no-motion',s.visual?.motion===false);for(const x of ['clean','game','neon','minimal'])document.body.classList.toggle('style-'+x,(s.visual?.style||'clean')===x);if(s.visual?.accent)document.documentElement.style.setProperty('--accent',s.visual.accent)}
function choices(q,correct=''){if(!q)return '';if(q.kind==='multiple')return '<div class="choices">'+(q.choices||[]).map((v,i)=>'<div class="choice '+(String(i+1)===String(correct)?'correct':'')+'"><span class="n">'+(i+1)+'</span><span>'+esc(v)+'</span></div>').join('')+'</div>';if(q.kind==='ox')return '<div class="choices"><div class="choice '+(String(correct).toUpperCase()==='O'?'correct':'')+'"><span class="n">O</span><span>맞다</span></div><div class="choice '+(String(correct).toUpperCase()==='X'?'correct':'')+'"><span class="n">X</span><span>아니다</span></div></div>';return ''}
function top(s){return '<div class="top"><div class="eyebrow">QUESTION '+(Number(s.questionIndex||0)+1)+' / '+Number(s.questionCount||0)+'</div><div class="chips"><span class="chip"><i class="dot"></i><b id="p">'+Number(s.participants||0).toLocaleString()+'</b>명</span><span id="a" class="chip">답변 '+Number(s.answered||0).toLocaleString()+'</span>'+(Number(s.eliminated||0)>0?'<span id="survive" class="chip">생존 '+Number(s.survivors||0).toLocaleString()+'</span>':'')+'</div></div>'}
function answerText(q){if(!q||q.answer===undefined)return '';if(q.kind==='multiple'){const i=Number(q.answer)-1;return esc(q.answer)+' · '+esc((q.choices||[])[i]||'')}if(q.kind==='ox')return esc(String(q.answer).toUpperCase())+' · '+(String(q.answer).toUpperCase()==='O'?'맞다':'아니다');if(q.kind==='number'&&q.number_mode==='closest')return '기준값 '+esc(q.answer);return esc(q.answer)}
function sceneKey(s){const q=s.question||{};return [s.state,s.questionIndex,s.questionKey||'',q.answer===undefined?'':q.answer].join(':')}
function stopTimer(){if(tm){clearInterval(tm);tm=0}}function timer(){stopTimer();const r=()=>{if(!S||S.state!=='ANSWERING')return;const left=Math.max(0,Number(S.deadlineEpochMs||0)-Date.now()),el=document.querySelector('#timer'),bar=document.querySelector('#bar');if(el)el.textContent=(left/1000).toFixed(1)+'초';if(bar){const total=Math.max(1000,Number(S.question?.duration_sec||1)*1000);bar.style.width=Math.max(0,Math.min(100,left/total*100))+'%'}};r();tm=setInterval(r,100)}
function fitLayout(){if(!CARD)return;for(const c of ['fit-1','fit-2','fit-3','fit-4'])CARD.classList.remove(c);const tooTall=()=>CARD.scrollHeight>CARD.clientHeight+2;for(const c of ['fit-1','fit-2','fit-3','fit-4']){if(!tooTall())break;CARD.classList.add(c)}document.body.dataset.overflow=tooTall()?'1':'0';document.body.dataset.scene=S?.state||''}
function afterRender(){requestAnimationFrame(()=>requestAnimationFrame(fitLayout))}
function render(s){stopTimer();scene=sceneKey(s);const q=s.question;if(['DISCONNECTED','READY'].includes(s.state)){C.innerHTML='<div class="hero enter"><div class="k">SOOP LIVE QUIZ</div><div class="t">QUIZ</div><div class="s">진행자 프로그램에서 퀴즈를 시작해주세요</div></div>';afterRender();return}if(s.state==='RECRUITING'){C.innerHTML='<div class="hero pop"><div class="k">NOW OPEN</div><div class="t">참가 모집</div><div class="s">채팅에 <b class="accent">!참여</b> · 현재 <b id="recruit" class="accent">'+Number(s.participants||0).toLocaleString()+'</b>명</div></div>';afterRender();return}if(s.state==='LOCKED'){C.innerHTML='<div class="hero enter"><div class="k">READY</div><div class="t"><b id="lockedCount">'+Number(s.participants||0).toLocaleString()+'</b>명 참가</div><div class="s">진행자가 문제를 공개하면 화면에 문제가 표시됩니다</div></div>';afterRender();return}if(s.state==='QUESTION_VOID'){C.innerHTML='<div class="hero pop"><div class="k">VOID</div><div class="t">문제 무효</div><div class="s">이 문제의 점수는 반영되지 않습니다 · 다음 문제를 준비합니다</div></div>';afterRender();return}if(s.state==='FINISHED'){C.innerHTML='<div class="hero pop"><div class="k">FINAL</div><div class="t">QUIZ END</div><div class="s">최종 순위를 확인해주세요</div></div>';afterRender();return}if(!q){C.innerHTML='<div class="hero"><div class="k">CHECK</div><div class="t">문제 없음</div><div class="s">진행자 프로그램에서 문제 설정을 확인해주세요</div></div>';afterRender();return}
if(s.state==='QUESTION_SHOWN'){C.innerHTML=top(s)+'<div class="q enter">'+esc(q.prompt)+'</div>'+choices(q)+'<div class="foot"><div><div class="instruction">문제 공개 · <span class="accent">아직 답변은 받지 않습니다</span></div><div class="hint">진행자가 START를 누른 이후 입력한 답변만 인정됩니다</div></div><span class="chip">START 대기</span></div>';afterRender();return}
if(s.state==='ANSWERING'){C.innerHTML=top(s)+'<div class="q">'+esc(q.prompt)+'</div>'+choices(q)+'<div class="foot"><div><div class="instruction"><span class="accent pop">START</span> · 정답을 입력하세요</div><div class="hint">'+esc(s.answerHint||'')+'</div></div><div id="timer" class="timer"></div></div><div class="bar"><i id="bar"></i></div>';timer();afterRender();return}
if(s.state==='QUESTION_CLOSED'){C.innerHTML=top(s)+'<div class="q">'+esc(q.prompt)+'</div>'+choices(q)+'<div class="foot"><div><div class="instruction">답변 마감</div><div class="hint"><b id="closedAnswered" class="accent">'+Number(s.answered||0).toLocaleString()+'</b>명 답변 · 정답 공개를 기다려주세요</div></div><span class="chip">CLOSED</span></div>';afterRender();return}
if(s.state==='ANSWER_REVEALED'){const fast=(s.visual?.showFastest===false?[]:(s.firstCorrect||[]).slice(0,3)).map(x=>'<span>'+Number(x.rank||0)+'위 '+esc(x.display)+' · '+(Number(x.elapsedMs||0)/1000).toFixed(3)+'초</span>').join('');C.innerHTML=top(s)+'<div class="q">'+esc(q.prompt)+'</div>'+choices(q,String(q.answer))+'<div class="answer-banner pop"><span class="answer-label">정답</span><span>'+answerText(q)+'</span></div><div class="foot"><div><div class="instruction">정답자 <b id="resultCorrect" class="good">'+Number(s.correct||0).toLocaleString()+'</b>명</div><div class="hint">정답률 <span id="rate">'+(Number(s.answered||0)?((Number(s.correct||0)/Number(s.answered||1))*100).toFixed(1):'0.0')+'</span>%'+(Number(q.score_multiplier||1)!==1?' · '+Number(q.score_multiplier||1)+'배 배점':'')+'</div><div class="fast">'+fast+'</div></div><span class="chip">RESULT</span></div>';afterRender();return}afterRender()}
function setText(id,value){const e=document.getElementById(id);if(e)e.textContent=value}function patch(s){const k=sceneKey(s);if(k!==scene)return render(s);setText('p',Number(s.participants||0).toLocaleString());setText('recruit',Number(s.participants||0).toLocaleString());setText('lockedCount',Number(s.participants||0).toLocaleString());setText('a','답변 '+Number(s.answered||0).toLocaleString());setText('survive','생존 '+Number(s.survivors||0).toLocaleString());setText('closedAnswered',Number(s.answered||0).toLocaleString());if(s.state==='ANSWER_REVEALED'){setText('resultCorrect',Number(s.correct||0).toLocaleString());setText('rate',Number(s.answered||0)?((Number(s.correct||0)/Number(s.answered||1))*100).toFixed(1):'0.0')}afterRender()}
function apply(s){if(!s||typeof s!=='object')return;S=s;visual(s);W.classList.toggle('hidden',!s.integrityWarning);W.textContent=s.integrityWarning||'';patch(s)}async function sync(){try{const r=await fetch('/api/state',{cache:'no-store'});if(!r.ok)throw new Error('state '+r.status);apply(await r.json());NET.classList.add('hidden')}catch{NET.classList.remove('hidden')}}
function events(){if(!window.EventSource){setInterval(sync,2000);return}if(es)try{es.close()}catch{}es=new EventSource('/api/events');es.onopen=()=>NET.classList.add('hidden');es.onmessage=x=>{try{apply(JSON.parse(x.data));NET.classList.add('hidden')}catch{}};es.onerror=()=>{NET.classList.remove('hidden');setTimeout(sync,650)}}
window.addEventListener('resize',()=>requestAnimationFrame(fitLayout));sync().then(events);
</script></body></html>'''


class HandlerV9(BaseHTTPRequestHandler):
    engine: QuizEngineV9
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args) -> None:
        return

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _events(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        last = -1
        try:
            self.wfile.write(b"retry: 1000\n\n")
            self.wfile.flush()
            while True:
                version = self.engine.wait_for_update(last, timeout=10.0)
                if version <= last:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue

                # Coalesce bursts from chat answers, but bind the cursor to the
                # exact snapshot we actually send. v0.5-v0.8 used the engine's
                # *later* version after serialization, which could skip a state
                # change that happened between snapshot and cursor update.
                time.sleep(0.035)
                state = self.engine.public_state()
                snapshot_version = int(state.get("stateVersion") or 0)
                if snapshot_version <= last:
                    continue
                payload = json.dumps(state, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                self.wfile.write(f"id: {snapshot_version}\n".encode("ascii"))
                self.wfile.write(b"data: " + payload + b"\n\n")
                self.wfile.flush()
                last = snapshot_version
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/state":
            body = json.dumps(self.engine.public_state(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")
        elif path == "/api/events":
            self._events()
        elif path == "/api/health":
            self._send(200, json.dumps({"ok": True, "version": UI_VERSION, "transport": "sse-v2"}, separators=(",", ":")).encode(), "application/json")
        elif path in {"/", "/overlay/quiz"}:
            self._send(200, QUIZ.encode("utf-8"), "text/html; charset=utf-8")
        elif path in {"/overlay/rank", "/overlay/top10", "/overlay/top3"}:
            self._send(200, legacy.RANK.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/overlay/status":
            self._send(200, legacy.STATUS.encode("utf-8"), "text/html; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain; charset=utf-8")


class OverlayServerV9:
    def __init__(self, engine: QuizEngineV9, preferred_port: int = 8765) -> None:
        self.engine = engine
        self.port = self._find_port(preferred_port)
        bound_handler = type("BoundHandlerV9", (HandlerV9,), {"engine": engine})
        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), bound_handler)
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
    def quiz_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/overlay/quiz"

    @property
    def rank_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/overlay/top10"

    @property
    def top3_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/overlay/top3?limit=3"

    @property
    def status_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/overlay/status"

    @property
    def health_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/api/health"

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True, name="overlay-http-v9")
        self.thread.start()

    def is_healthy(self) -> bool:
        return bool(self.thread and self.thread.is_alive())

    def stop(self) -> None:
        try:
            self.server.shutdown()
            self.server.server_close()
        except Exception:
            pass
