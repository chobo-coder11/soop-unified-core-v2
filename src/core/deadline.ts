export class DeadlineExceededError extends Error {
  constructor(readonly label:string, readonly timeoutMs:number){super(`${label} timeout after ${timeoutMs}ms`);this.name='DeadlineExceededError'}
}

export async function withDeadline<T>(promise:Promise<T>,timeoutMs:number,label='operation'):Promise<T>{
  if(!Number.isFinite(timeoutMs)||timeoutMs<=0)return promise;
  let timer:NodeJS.Timeout|undefined;
  const timeout=new Promise<never>((_,reject)=>{timer=setTimeout(()=>reject(new DeadlineExceededError(label,timeoutMs)),timeoutMs)});
  try{return await Promise.race([promise,timeout])}finally{if(timer)clearTimeout(timer)}
}
