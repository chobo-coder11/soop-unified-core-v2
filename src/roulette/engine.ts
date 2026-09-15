import{createHash,randomInt,randomUUID}from'node:crypto';

export type BoxStatus='collecting'|'completed'|'archived';
export interface Share{userId:string;nickname:string;amount:number}
export interface RouletteBox{id:string;code:string;title:string;goal:number;collected:number;status:BoxStatus;shares:Share[];winner?:Share;createdAt:string;completedAt?:string}
export interface PendingBalance{userId:string;nickname:string;amount:number}
export interface RouletteHistory{id:string;kind:string;at:string;boxId?:string;detail:Record<string,unknown>}
export interface RouletteState{version:1;streamerId:string;activeBoxId?:string;overlay:{x:number;y:number;scale:number};boxes:RouletteBox[];pending:PendingBalance[];history:RouletteHistory[];seenEventIds:string[]}

const empty=():RouletteState=>({version:1,streamerId:'',overlay:{x:4,y:72,scale:1.45},boxes:[],pending:[],history:[],seenEventIds:[]});
const cleanCode=(v:string)=>v.trim().replace(/^[#!]/,'').replace(/\s+/g,'').toLocaleLowerCase('ko-KR').slice(0,20);
const validAmount=(v:number)=>Number.isSafeInteger(v)&&v>0&&v<=100_000_000;

export class RouletteEngine{
  state:RouletteState;
  constructor(initial?:RouletteState){this.state=initial??empty();this.state.overlay??={x:4,y:72,scale:1.45}}
  setStreamer(id:string){this.state.streamerId=id.trim()}
  setActiveBox(id:string){const box=this.box(id);if(box.status!=='collecting')throw new Error('진행 중인 상자만 대표 상자로 선택할 수 있습니다.');this.state.activeBoxId=id;return box}
  setOverlay(v:{x:number;y:number;scale:number}){this.state.overlay={x:Math.max(0,Math.min(90,v.x)),y:Math.max(0,Math.min(90,v.y)),scale:Math.max(.6,Math.min(2.5,v.scale))};return this.state.overlay}
  createBox(input:{title?:string;code?:string;goal:number}){
    if(!validAmount(input.goal))throw new Error('목표 개수는 1개 이상이어야 합니다.');
    const title=(input.title?.trim()||`상자 ${this.state.boxes.filter(x=>x.status==='collecting').length+1}`).slice(0,30);
    const base=cleanCode(input.code||title)||String(this.state.boxes.length+1);
    let code=base,n=2;while(this.state.boxes.some(x=>x.status==='collecting'&&x.code===code))code=`${base}${n++}`;
    const box:RouletteBox={id:randomUUID(),code,title,goal:input.goal,collected:0,status:'collecting',shares:[],createdAt:new Date().toISOString()};
    this.state.boxes.push(box);if(!this.state.boxes.some(x=>x.id===this.state.activeBoxId&&x.status==='collecting'))this.state.activeBoxId=box.id;this.log('box_created',{title,code,goal:box.goal},box.id);return box;
  }
  archiveBox(id:string){const box=this.box(id);if(box.status==='collecting'&&box.collected)for(const share of box.shares)this.addPending(share);box.status='archived';if(this.state.activeBoxId===id)this.state.activeBoxId=this.state.boxes.find(x=>x.status==='collecting')?.id;this.log('box_archived',{title:box.title},id);return box}
  processDonation(input:{eventId:string;userId?:string;nickname?:string;amount:number;message?:string},pick?:(max:number)=>number){
    if(!validAmount(input.amount))return{accepted:false,reason:'invalid_amount'} as const;
    if(this.state.seenEventIds.includes(input.eventId))return{accepted:false,reason:'duplicate'} as const;
    this.state.seenEventIds.push(input.eventId);if(this.state.seenEventIds.length>5000)this.state.seenEventIds.splice(0,this.state.seenEventIds.length-5000);
    const userId=(input.userId||input.nickname||'anonymous').slice(0,80),nickname=(input.nickname||'익명').slice(0,30);
    const box=this.findTarget(input.message||'');
    if(!box){this.addPending({userId,nickname,amount:input.amount});this.log('donation_pending',{nickname,amount:input.amount,message:input.message||''});return{accepted:true,pending:input.amount} as const}
    const pending=this.takePending(userId),total=pending+input.amount,result=this.allocate(box,{userId,nickname,amount:total},pick);
    this.log('donation_allocated',{nickname,donation:input.amount,pendingApplied:pending,allocated:result.allocated,overflow:result.overflow},box.id);
    return{accepted:true,box,winner:result.winner,allocated:result.allocated,overflow:result.overflow} as const;
  }
  assignPending(userId:string,boxId:string,pick?:(max:number)=>number){const box=this.box(boxId),p=this.state.pending.find(x=>x.userId===userId),nickname=p?.nickname||userId,amount=this.takePending(userId);if(!amount)throw new Error('배정할 잔액이 없습니다.');return this.allocate(box,{userId,nickname,amount},pick)}
  rollPendingInto(boxId:string,pick?:(max:number)=>number){const box=this.box(boxId),users=this.state.pending.map(x=>x.userId);let allocated=0,overflow=0,winner:Share|undefined;for(const userId of users){if(box.status!=='collecting')break;const result=this.assignPending(userId,boxId,pick);allocated+=result.allocated;overflow+=result.overflow;if(result.winner)winner=result.winner}if(allocated)this.log('pending_rolled_over',{allocated,remaining:this.state.pending.reduce((n,x)=>n+x.amount,0)},boxId);return{box,allocated,overflow,winner}}
  private allocate(box:RouletteBox,share:Share,pick?:(max:number)=>number){if(box.status!=='collecting')throw new Error('이미 종료된 상자입니다.');const allocated=Math.min(share.amount,box.goal-box.collected),overflow=share.amount-allocated;const old=box.shares.find(x=>x.userId===share.userId);if(old){old.amount+=allocated;old.nickname=share.nickname}else box.shares.push({...share,amount:allocated});box.collected+=allocated;if(overflow)this.addPending({...share,amount:overflow});let winner:Share|undefined;if(box.collected>=box.goal){box.status='completed';box.completedAt=new Date().toISOString();winner=this.pickWinner(box,pick);box.winner={...winner};if(this.state.activeBoxId===box.id)this.state.activeBoxId=this.state.boxes.find(x=>x.status==='collecting')?.id;this.log('winner_selected',{nickname:winner.nickname,userId:winner.userId,amount:winner.amount,total:box.collected,audit:this.audit(box)},box.id)}return{allocated,overflow,winner}}
  private pickWinner(box:RouletteBox,pick?:(max:number)=>number){let ticket=(pick??randomInt)(box.collected);for(const share of box.shares){ticket-=share.amount;if(ticket<0)return share}throw new Error('추첨할 참여자가 없습니다.')}
  private findTarget(message:string){const active=this.state.boxes.filter(x=>x.status==='collecting');const tokens=[...message.matchAll(/(?:^|\s)[#!]([^\s#!]+)/g)].map(x=>cleanCode(x[1]));const exact=active.filter(b=>tokens.includes(b.code));if(exact.length===1)return exact[0];if(tokens.length)return undefined;const normalized=cleanCode(message),mentions=active.filter(b=>normalized.includes(b.code)&&b.code.length>=2);if(mentions.length===1)return mentions[0];return active.find(x=>x.id===this.state.activeBoxId)}
  private addPending(share:Share){const p=this.state.pending.find(x=>x.userId===share.userId);if(p){p.amount+=share.amount;p.nickname=share.nickname}else this.state.pending.push({...share})}
  private takePending(userId:string){const i=this.state.pending.findIndex(x=>x.userId===userId);if(i<0)return 0;return this.state.pending.splice(i,1)[0].amount}
  private box(id:string){const box=this.state.boxes.find(x=>x.id===id);if(!box)throw new Error('상자를 찾을 수 없습니다.');return box}
  private audit(box:RouletteBox){return createHash('sha256').update(JSON.stringify({id:box.id,goal:box.goal,shares:box.shares,completedAt:box.completedAt})).digest('hex').slice(0,16)}
  private log(kind:string,detail:Record<string,unknown>,boxId?:string){this.state.history.unshift({id:randomUUID(),kind,at:new Date().toISOString(),boxId,detail});this.state.history=this.state.history.slice(0,500)}
}
