import{readFileSync}from'node:fs';import{resolve}from'node:path';
const root=process.env.SOOP_APP_ROOT||process.cwd();
const page=(name:string)=>readFileSync(resolve(root,'desktop',name),'utf8');
export const ROULETTE_ADMIN_HTML=page('admin.html');
export const ROULETTE_OVERLAY_HTML=page('overlay.html');
export const ROULETTE_ADMIN_JS=page('admin.js');
export const ROULETTE_OVERLAY_JS=page('overlay.js');
