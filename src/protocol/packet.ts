import {ESC,F} from './constants.js';
export interface ParsedPacket{code:number;declaredLength:number;actualLength:number;lengthValid:boolean;payload:string;parts:string[];raw:string}
export const byteLengthUtf8=(input:string)=>Buffer.byteLength(input,'utf8');
export function buildPacket(code:number,payload:string){return `${ESC}${String(code).padStart(4,'0')}${String(byteLengthUtf8(payload)).padStart(6,'0')}00${payload}`}
export function parsePacket(raw:string):ParsedPacket{
  if(!raw.startsWith(ESC))throw new Error('Invalid SOOP packet starter');
  if(raw.length<14)throw new Error('SOOP packet too short');
  const code=Number(raw.slice(2,6)),declaredLength=Number(raw.slice(6,12));
  if(!Number.isInteger(code)||!Number.isInteger(declaredLength))throw new Error('Invalid SOOP packet header');
  const wirePayload=raw.slice(14),actualLength=byteLengthUtf8(wirePayload),idx=wirePayload.indexOf(F);
  const payload=idx>=0?wirePayload.slice(idx+1):wirePayload,parts=idx>=0?payload.split(F):[];
  return{code,declaredLength,actualLength,lengthValid:declaredLength===actualLength,payload,parts,raw};
}
