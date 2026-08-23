export interface BroadcastGenerationState{
  streamerId:string;
  bno:string;
  generation:number;
  firstSeenAt:string;
  lastSeenAt:string;
  previousBno?:string;
  changes:number;
}
export interface BroadcastGenerationObservation extends BroadcastGenerationState{changed:boolean}

/** Tracks broadcast identity changes so stale data from an older BNO is never silently mixed into a new broadcast. */
export class BroadcastGenerationTracker{
  private states=new Map<string,BroadcastGenerationState>();
  observe(streamerId:string,bno:string|undefined,at=new Date().toISOString()):BroadcastGenerationObservation|undefined{
    if(!bno)return undefined;const old=this.states.get(streamerId);
    if(!old){const next:BroadcastGenerationState={streamerId,bno,generation:1,firstSeenAt:at,lastSeenAt:at,changes:0};this.states.set(streamerId,next);return{...next,changed:true}}
    if(old.bno===bno){old.lastSeenAt=at;return{...old,changed:false}}
    const next:BroadcastGenerationState={streamerId,bno,generation:old.generation+1,firstSeenAt:at,lastSeenAt:at,previousBno:old.bno,changes:old.changes+1};this.states.set(streamerId,next);return{...next,changed:true}
  }
  get(streamerId:string){const x=this.states.get(streamerId);return x?{...x}:undefined}
  snapshot(){return[...this.states.values()].map(x=>({...x}))}
  delete(streamerId:string){this.states.delete(streamerId)}
}
