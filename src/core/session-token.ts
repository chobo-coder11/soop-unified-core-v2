import{createHash,randomBytes}from'node:crypto';
export const createSessionToken=()=>randomBytes(32).toString('base64url');
export const hashSessionToken=(token:string)=>createHash('sha256').update(token).digest('hex');
export const sessionRefFromHash=(hash:string)=>hash.slice(0,12);
