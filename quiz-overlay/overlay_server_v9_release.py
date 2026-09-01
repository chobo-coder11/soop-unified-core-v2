from __future__ import annotations

"""Final v0.9 overlay hotfix applied before the release entry point imports app_v9.

Keeping this patch isolated lets the underlying v0.9 regression explain the exact
root cause while the shipped build uses the corrected viewport measurement.
"""

import overlay_server_v9 as _base

_original = _base.QUIZ
_fixed = _original
_fixed = _fixed.replace(
    '.shell{width:100%;height:100%;display:flex;align-items:center;justify-content:center;padding:clamp(8px,1.8vh,20px) clamp(10px,2vw,36px)}',
    '.shell{width:100%;height:100%;display:flex;align-items:center;justify-content:center;padding:8px 10px}',
)
_fixed = _fixed.replace(
    'function fitLayout(){if(!CARD)return;for(const c of [\'fit-1\',\'fit-2\',\'fit-3\',\'fit-4\'])CARD.classList.remove(c);const tooTall=()=>CARD.scrollHeight>CARD.clientHeight+2;for(const c of [\'fit-1\',\'fit-2\',\'fit-3\',\'fit-4\']){if(!tooTall())break;CARD.classList.add(c)}document.body.dataset.overflow=tooTall()?\'1\':\'0\';document.body.dataset.scene=S?.state||\'\'}',
    'function fitLayout(){if(!CARD)return;for(const c of [\'fit-1\',\'fit-2\',\'fit-3\',\'fit-4\'])CARD.classList.remove(c);const tooTall=()=>{const r=CARD.getBoundingClientRect();return CARD.scrollHeight>CARD.clientHeight+2||r.top<0||r.bottom>window.innerHeight-1};for(const c of [\'fit-1\',\'fit-2\',\'fit-3\',\'fit-4\']){if(!tooTall())break;CARD.classList.add(c)}document.body.dataset.overflow=tooTall()?\'1\':\'0\';document.body.dataset.scene=S?.state||\'\';document.body.dataset.answerVisible=document.querySelector(\'.answer-banner\')?\'1\':\'0\'}',
)

if _fixed == _original:
    raise RuntimeError('v0.9 release overlay patch did not match expected source')
if 'data' not in _fixed or 'dataset.answerVisible' not in _fixed:
    raise RuntimeError('v0.9 release overlay patch incomplete')

_base.QUIZ = _fixed
QUIZ = _fixed
HandlerV9 = _base.HandlerV9
OverlayServerV9 = _base.OverlayServerV9
