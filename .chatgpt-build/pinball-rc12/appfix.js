const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
let S=null, selected=new Set(), hideCopied=true;
const api=async(path,body)=>{const r=await fetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});return r.json()};
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const fmt=n=>Number(n||0).toLocaleString('ko-KR');
const time=t=>t?new Date(t).toLocaleTimeString('ko-KR',{timeZone:'Asia/Seoul',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}):'';
const pad=n=>String(n).padStart(2,'0');
const dur=ms=>{ms=Math.max(0,ms||0);const s=Math.floor(ms/1000),h=Math.floor(s/3600),m=Math.floor((s%3600)/60),ss=s%60;return h?`${pad(h)}:${pad(m)}:${pad(ss)}`:`${pad(m)}:${pad(ss)}`};
const parseClockInput=v=>{v=String(v||'').trim();if(/^\d{1,2}:\d{2}$/.test(v))v+=':00';const m=v.match(/^(\d{1,2}):(\d{2}):(\d{2})$/);if(!m)return null;const h=+m[1],mi=+m[2],ss=+m[3];if(h>23||mi>59||ss>59)return null;return `${pad(h)}:${pad(mi)}:${pad(ss)}`};
const clockValue=(v,f='20:00:00')=>parseClockInput(v)||f;
function toast(t){const x=$('#toast');x.textContent=t;x.classList.add('show');clearTimeout(x._t);x._t=setTimeout(()=>x.classList.remove('show'),1700)}
async function copyText(t){if(!t)return false;try{await navigator.clipboard.writeText(t);return true}catch{const ta=document.createElement('textarea');ta.value=t;document.body.appendChild(ta);ta.select();const ok=document.execCommand('copy');ta.remove();return ok}}
function kindName(k){return {star_balloon:'일반 별풍선',star_balloon_sub:'일반 별풍선',adcon:'애드벌룬',station_adcon:'애드벌룬',video_balloon:'영상풍선',mission:'미션 별풍선'}[k]||k}
function statusLabel(q){return q.status==='waiting_tts'?['전자녀 대기','wait']:q.status==='review'?['확인 필요','review']:q.status==='copied'?['복사됨','copied']:q.status==='processed'?['처리 완료','processed']:q.status==='skipped'?['제외','processed']:['준비됨','ready']}
function readyItems(){return (S?.queue||[]).filter(x=>x.status==='ready')}
function pendingItems(){return (S?.queue||[]).filter(x=>['ready','waiting_tts','review'].includes(x.status))}
function effectiveSelection(){const ids=[...selected].filter(id=>S.queue.some(x=>x.id===id&&['ready','copied'].includes(x.status)));return ids.length?ids:readyItems().map(x=>x.id)}
function render(){if(!S)return;
  $('#ver').textContent=S.version;
  $('#statDonations').textContent=fmt(S.sessionDonationCount);
  $('#statBalls').textContent=fmt(S.sessionBalls);
  $('#statPending').textContent=fmt(pendingItems().length);
  const dot=$('#statusDot');dot.className='statusDot '+(S.connected?'on':S.connecting?'wait':'off');
  $('#statusText').textContent=S.connectionState||'연결 안 됨';
  $('#lastInbound').textContent=S.lastInbound?`마지막 이벤트 ${time(S.lastInbound)}`:(S.error||'SOOP ID 또는 방송 URL을 연결하세요');
  $('#liveBadge').textContent=S.connected?'LIVE':S.connecting?'CONNECTING':'OFFLINE';$('#liveBadge').classList.toggle('live',S.connected);
  $('#healthSocket').className='healthDot '+(S.connected?'ok':S.connecting?'wait':'');$('#healthSocketText').textContent=S.connected?'정상':S.connecting?'재연결':'대기';
  const buffered=Number(S.ingestBuffered||0),capacity=Number(S.ingestCapacity||65536);const bd=$('#healthBuffer'),bt=$('#healthBufferText');if(bd&&bt){bd.className='healthDot '+(buffered===0?'ok':buffered<Math.max(32,capacity*0.25)?'wait':'');bt.textContent=buffered===0?'여유':`${fmt(buffered)}건 처리 대기`;}
  const activeConnection=!!(S.connected||S.connecting);$('#broadcastEmpty').classList.toggle('hidden',activeConnection);$('#broadcastIdentity').classList.toggle('hidden',!activeConnection);const ci=$('.connectInline');if(ci)ci.classList.toggle('hidden',activeConnection);const db=$('#disconnectBtn');if(db){db.disabled=!activeConnection;db.title=db.disabled?'현재 SOOP 소켓이 연결되어 있지 않습니다.':'SOOP 실시간 연결만 중단합니다.';}
  if(activeConnection){$('#streamNick').textContent=S.streamerNick||S.config.streamerId||'연결 중';$('#streamId').textContent=S.config.streamerId||'-';}
  const cb=$('#connectBtn');if(cb&&!activeConnection)cb.textContent=(S.config.streamInput||S.config.streamerId)?'다시 연결':'연결';
  $('#summaryRate').textContent=fmt(S.config.rate);$('#summaryMode').textContent=S.config.mode==='tts'?'전자녀':'닉네임(ID)';$('#modeIndicator').textContent=S.config.mode==='tts'?'전자녀 수집 모드':'닉네임(ID) 수집 모드';
  $('#ttsSummary').classList.toggle('hidden',S.config.mode!=='tts');$('#summaryTTS').textContent=`${S.config.ttsWindow}초`;
  $('#lockBadge').textContent=S.config.locked?'설정 잠김':'편집 가능';$('#lockBadge').classList.toggle('locked',S.config.locked);
  renderKindsSummary();renderSchedule();renderCurrentEvent();renderQueue();renderFeed();syncControls(false);renderCopyDock();
}
function schedulePhaseText(p){return p==='waiting'?'예약 대기':p==='collecting'?'자동 수집 중':p==='grace'?'신규 후원 마감 · 전자녀 처리 중':p==='finished'?'예약 종료':'수동 수집'}
function scheduleRange(){const c=S?.config||{};if(!c.scheduledStartAt||!c.scheduledEndAt)return '';const a=new Date(c.scheduledStartAt),b=new Date(c.scheduledEndAt);const f=d=>`${d.toLocaleDateString('ko-KR',{timeZone:'Asia/Seoul',month:'numeric',day:'numeric'})} ${d.toLocaleTimeString('ko-KR',{timeZone:'Asia/Seoul',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false})}`;return `${f(a)} → ${f(b)}`}
function renderSchedule(){if(!S)return;const c=S.config||{}, scheduled=c.collectionMode==='scheduled',phase=S.schedulePhase||'manual',now=S.serverNow?new Date(S.serverNow):new Date(),start=c.scheduledStartAt?new Date(c.scheduledStartAt):null,end=c.scheduledEndAt?new Date(c.scheduledEndAt):null;
  $('#summarySchedule').textContent=!scheduled?'수동 · 항상 수집':(c.scheduleArmed&&start&&end?`${time(start)} → ${time(end)}`:'시간 지정 · 예약 없음');
  $('#scheduleMini').classList.toggle('hidden',!scheduled);if(scheduled){$('#scheduleMiniTitle').textContent=schedulePhaseText(phase);$('#scheduleMiniTime').textContent=c.scheduleArmed&&start&&end?scheduleRange():'예약 시간을 설정하세요';$('#scheduleMini').className='scheduleMini '+(phase==='collecting'?'active':phase==='grace'?'grace':phase==='waiting'?'waiting':'');}
  const si=$('#scheduleIndicator');si.classList.toggle('hidden',!scheduled);if(scheduled){si.textContent=schedulePhaseText(phase);si.className='scheduleIndicator '+(phase==='collecting'?'active':phase==='grace'?'grace':'');}
  $('#scheduleOptions').classList.toggle('hidden',!scheduled);
  $('#serverClock').textContent=S.serverNow?time(S.serverNow):'--:--:--';$('#serverClockState').textContent=`${S.timeSource||'KST'} · ${S.timeSyncStatus||'확인 중'}`;$('#serverClockDot').className=(S.timeSyncStatus==='정상'||S.timeSyncStatus==='마지막 동기화 유지')?'ok':'wait';
  const box=$('#activeScheduleBox');const show=scheduled&&(c.scheduleArmed||phase==='grace');box.classList.toggle('hidden',!show);
  if(show&&start&&end){$('#activeSchedulePhase').textContent=schedulePhaseText(phase);$('#activeScheduleRange').textContent=scheduleRange();let left=0,pct=0;if(phase==='waiting'){left=start-now; pct=0}else if(phase==='collecting'){left=end-now;const total=end-start,past=now-start;pct=Math.max(0,Math.min(100,past/total*100))}else if(phase==='grace'){left=0;pct=100}else{pct=100}$('#scheduleCountdown').textContent=phase==='grace'?`전자녀 ${S.schedulePendingTts||0}거`:phase==='finished':'종료':dur(left);$('#scheduleProgressBar').style.width=pct+'%';$('#scheduleGraceText').classList.toggle('hidden',phase!=='grace');}
  const sv=parseClockInput($('#scheduleStart')?.value)||c.scheduleStart||'20:00:00',ev=parseClockInput($('#scheduleEnd')?.value)||c.scheduleEnd||'21:00:00';if($('#scheduleDatePreview'))$('#scheduleDatePreview').textContent=ev<=sv?'좈료 시각이 시작보다 빠르미로 늴음 날 좈료로 자동 계산됩니다.':'현재 SOOP/KST날짜를 기준으로 가장 가까운 유한 구간을 자동 계삠합니다.';
}
function renderKindsSummary(){const c=S.config.donationTypes||{}, chips=[];if(c.star_balloon||c.star_balloon_sub)chips.push(['l이반',true]);if(c.adcon||c.station_adcon)chips.push(['e애드벌룬',true]);if(c.mission)chips.push(['e도전미션',true]);if(c.video_balloon)chips.push(['e영상',true]);if(!chips.length)chips.push(['선택 엄음',false]);$('#summaryKinds').innerHTML=chips.map(([x,on])=>`<span class="kindChip ${on?'on':''}">${x}</span>`).join('')}
function latestMeaningful(){return (S.queue||[]).find(x=>!['processed','skipped'].includes(x.status))||(S.queue||[])[0]}
function renderCurrentEvent(){const root=$('#currentEvent')