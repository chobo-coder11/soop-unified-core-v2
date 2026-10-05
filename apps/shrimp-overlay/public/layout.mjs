export const REFLOW_KEYS=Object.freeze(['size','bottom','fontFamily','fontWeight','fontSize','bubbleMaxWidth','bubbleMaxLines','bubblePadding','bubbleGap','emoteSize','namePosition','nameFontSize','namePaddingY','nameGap','showNames','spriteHeadRatio']);
export function requiresReflow(next,previous){return REFLOW_KEYS.some(k=>k in next&&next[k]!==previous[k]);}
const segmenter=new Intl.Segmenter('ko',{granularity:'grapheme'});
export function graphemes(text){return Array.from(segmenter.segment(text),x=>x.segment);}
export function borderWidth(value){const n=Number(value);return Number.isFinite(n)&&n>0?n:0;}
export class ReplayGuard {
 constructor(){this.seen=new Map();}
 accept(chat,now){const key=`${chat.streamerId}:${chat.id}`;for(const [k,t] of this.seen)if(now-t>30000)this.seen.delete(k);if(this.seen.has(key))return false;this.seen.set(key,now);while(this.seen.size>512)this.seen.delete(this.seen.keys().next().value);return true;}
 clear(){this.seen.clear();}
}
export function placeName(rect,occupied){return occupied.some(b=>rect.x<b.x+b.w+4&&rect.x+rect.w+4>b.x&&rect.y<b.y+b.h+2&&rect.y+rect.h+2>b.y)?null:rect;}
