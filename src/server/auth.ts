import{createHash,timingSafeEqual}from'node:crypto';
const digest=(v:string)=>createHash('sha256').update(v).digest();
export function secureTokenEqual(candidate:unknown,expected:string|undefined){if(!expected)return true;if(typeof candidate!=='string'||!candidate)return false;return timingSafeEqual(digest(candidate),digest(expected))}
