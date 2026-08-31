from __future__ import annotations

import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from engine import QuizEngine

QUIZ_HTML = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
html,body{margin:0;background:transparent;overflow:hidden;font-family:"Malgun Gothic","Noto Sans KR",sans-serif;color:#fff}*{box-sizing:border-box}.wrap{width:100vw;height:100vh;display:flex;align-items:center;justify-content:center;padding:3vw}.card{width:min(92vw,1500px);background:rgba(10,13,20,.88);border:2px solid rgba(255,255,255,.16);border-radius:28px;padding:40px 48px;box-shadow:0 20px 60px rgba(0,0,0,.35)}.top{display:flex;justify-content:space-between;align-items:center;font-size:24px;color:#c9d2e2;margin-bottom:24px}.q{font-size:clamp(34px,4vw,72px);font-weight:900;line-height:1.22;word-break:keep-all}.choices{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:28px}.choice{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);padding:20px 24px;border-radius:18px;font-size:clamp(24px,2.2vw,42px);font-weight:700}.status{margin-top:28px;text-align:center;font-size:clamp(24px,2.2vw,42px);font-weight:800}.timer{font-variant-numeric:tabular-nums;font-size:clamp(30px,3vw,52px);font-weight:900}.start{font-size:clamp(64px,9vw,150px);font-weight:1000;letter-spacing:.04em;text-align:center}.hint{text-align:center;margin-top:18px;font-size:clamp(24px,2vw,38px);font-weight:800}.answer{font-size:clamp(52px,6vw,110px);font-weight:1000;text-align:center;margin:20px 0}.mini{font-size:clamp(22px,1.8vw,34px);color:#dce3ee;text-align:center}.warn{position:absolute;left:2vw;bottom:2vw;background:rgba(145,35,35,.92);padding:10px 16px;border-radius:10px;font-size:18px}.hidden{display:none}.flash{animation:pulse .9s ease both}@keyframes pulse{0%{transform:scale(.88);opacity:0}55%{transform:scale(1.05);opacity:1}100%{transform:scale(1);opacity:1}}@media(max-width:900px){.choices{grid-template-columns:1fr}.card{padding:28px}}
</style></head><body><div class="wrap"><div id="card" class="card"><div id="content"></div></div></div><div id="warn" class="warn hidden"></div><script>
const $=s=>document.querySelector(s);let lastState='';function esc(s){return String(s??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}function cmd(q){if(!q)return'';if(q.kind==='multiple')return q.choices.map((_,i)=>'!'+(i+1)).join('   ');if(q.kind==='ox')return'!O   !X';if(q.kind==='short')return'!정답 [답변]';return'!숫자 2500  또는  !2500';}function render(s){const c=$('#content'),q=s.question;$('#warn').classList.toggle('hidden',!s.integrityWarning);$('#warn').textContent=s.integrityWarning||'';if(s.state==='DISCONNECTED'||s.state==='READY'){c.innerHTML='<div class="start">SOOP QUIZ</div><div class="hint">진행자 프로그램에서 시작해주세요</div>';return;}if(s.state==='RECRUITING'){c.innerHTML='<div class="start flash">참가 모집</div><div class="hint">채팅에 <b>!참여</b> 를 입력하세요</div><div class="status">현재 참가자 '+s.participants.toLocaleString()+'명</div>';return;}if(s.state==='LOCKED'){c.innerHTML='<div class="start">준비 완료</div><div class="hint">참가자 '+s.participants.toLocaleString()+'명 · 다음 문제를 준비합니다</div>';return;}if(!q){c.innerHTML='<div class="start">QUIZ</div>';return;}const top='<div class="top"><span>Q'+(s.questionIndex+1)+' / '+s.questionCount+'</span><span>참가 '+s.participants.toLocaleString()+'명</span></div>';const choices=q.kind==='multiple'?'<div class="choices">'+q.choices.map((x,i)=>'<div class="choice">'+(i+1)+'. '+esc(x)+'</div>').join('')+'</div>':q.kind==='ox'?'<div class="choices"><div class="choice">O</div><div class="choice">X</div></div>':'';if(s.state==='QUESTION_SHOWN'){c.innerHTML=top+'<div class="q">'+esc(q.prompt)+'</div>'+choices+'<div class="status">정답 입력 대기 중</div><div class="mini">진행자가 START를 누르면 입력해주세요</div>';return;}if(s.state==='ANSWERING'){let sec=s.remainingMs==null?'':(s.remainingMs/1000).toFixed(1)+'초';c.innerHTML=top+'<div class="start flash">START!</div><div class="q">'+esc(q.prompt)+'</div>'+choices+'<div class="status">정답을 입력해주세요!</div><div class="hint">'+esc(cmd(q))+'</div><div class="status timer">'+sec+'</div>';return;}if(s.state==='QUESTION_CLOSED'){c.innerHTML=top+'<div class="q">'+esc(q.prompt)+'</div>'+choices+'<div class="start">마감!</div><div class="hint">정답 입력이 종료되었습니다 · '+s.answered.toLocaleString()+'명 답변</div>';return;}if(s.state==='ANSWER_REVEALED'){let a=q.kind==='multiple'?(q.answer+'. '+esc(q.choices[Number(q.answer)-1]||'')):esc(q.answer);let fastest=s.firstCorrect.slice(0,3).map(x=>'<div class="mini">'+x.rank+'위 '+esc(x.display)+' · '+(x.elapsedMs/1000).toFixed(3)+'초</div>').join('');c.innerHTML=top+'<div class="mini">정답은</div><div class="answer flash">'+a+'</div><div class="status">정답자 '+s.correct.toLocaleString()+'명</div>'+fastest;return;}if(s.state==='FINISHED'){c.innerHTML='<div class="start flash">QUIZ END</div><div class="hint">최종 순위를 확인해주세요</div>';}}
async function tick(){try{const r=await fetch('/api/state?ts='+Date.now(),{cache:'no-store'});render(await r.json());}catch(e){}setTimeout(tick,180)}tick();</script></body></html>'''

RANK_HTML = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
html,body{margin:0;background:transparent;font-family:"Malgun Gothic","Noto Sans KR",sans-serif;color:#fff}*{box-sizing:border-box}.panel{margin:2vw;width:min(96vw,760px);background:rgba(10,13,20,.88);border:2px solid rgba(255,255,255,.15);border-radius:24px;padding:26px 30px}.title{font-size:42px;font-weight:1000;margin-bottom:6px}.sub{font-size:18px;color:#c9d2e2;margin-bottom:18px}.row{display:grid;grid-template-columns:58px 1fr 130px;gap:10px;align-items:center;padding:12px 4px;border-top:1px solid rgba(255,255,255,.1);font-size:24px}.rank{font-size:30px;font-weight:1000}.name{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:800}.value{text-align:right;font-weight:900}.empty{padding:30px 0;color:#cbd2dd;text-align:center;font-size:22px}</style></head><body><div class="panel"><div class="title">TOP 10</div><div id="sub" class="sub"></div><div id="rows"></div></div><script>
function esc(s){return String(s??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}async function tick(){try{const s=await (await fetch('/api/state?ts='+Date.now(),{cache:'no-store'})).json();const mode=s.rankingMode;document.querySelector('#sub').textContent=mode==='score'?'점수 기준':mode==='streak'?'최고 연속 정답 기준':'맞힌 개수 기준';const rows=s.ranking||[];document.querySelector('#rows').innerHTML=rows.length?rows.map(x=>'<div class="row"><div class="rank">'+x.rank+'</div><div class="name">'+esc(x.display)+'</div><div class="value">'+(mode==='score'?x.score.toLocaleString()+'점':mode==='streak'?x.streak+'연속':x.correct+'개')+'</div></div>').join(''):'<div class="empty">아직 순위가 없습니다</div>';}catch(e){}setTimeout(tick,250)}tick();</script></body></html>'''


class OverlayHandler(BaseHTTPRequestHandler):
    engine: QuizEngine = None  # type: ignore

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/state":
            body = json.dumps(self.engine.public_state(), ensure_ascii=False).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")
        elif path in {"/", "/overlay/quiz"}:
            self._send(200, QUIZ_HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/overlay/ranking":
            self._send(200, RANK_HTML.encode("utf-8"), "text/html; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain")


class OverlayServer:
    def __init__(self, engine: QuizEngine, port: int) -> None:
        OverlayHandler.engine = engine
        self.server = ThreadingHTTPServer(("127.0.0.1", port), OverlayHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.port = port

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        try:
            self.server.shutdown()
            self.server.server_close()
        except Exception:
            pass
