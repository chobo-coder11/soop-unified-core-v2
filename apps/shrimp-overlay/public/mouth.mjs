import { graphemes } from './layout.mjs';
// Mouth rectangles are fractions of an atlas cell, calibrated against its artwork.
// Closed artwork remains the body; only this small facial region can change.
export const MOUTHS = Object.freeze({
 shrimp:{closed:[.427,.554,.10,.09],open:[.465,.505,.10,.09]},
 duck:{closed:[.537,.561,.20,.16],open:[.542,.517,.20,.16]},
 sparrow:{closed:[.535,.477,.14,.13],open:[.568,.41,.14,.13]},
 seal:{closed:[.595,.683,.14,.09],open:[.565,.666,.14,.09]},
 tissue:{closed:[.58,.632,.105,.085],open:[.598,.562,.105,.085]},
 'purple-bee':{closed:[.584,.649,.105,.085],open:[.606,.551,.105,.085]},
 fries:{closed:[.585,.65,.10,.085],open:[.596,.576,.10,.085]},
 rose:{closed:[.54,.555,.10,.085],open:[.556,.505,.10,.085]},
 gorilla:{closed:[.558,.536,.10,.075],open:[.596,.503,.10,.075]},
 'purple-octopus':{closed:[.575,.645,.12,.105],open:[.557,.60,.12,.105]},
 'tea-bag':{closed:[.6,.616,.095,.075],open:[.613,.557,.095,.075]},
 squirrel:{closed:[.653,.565,.12,.08],open:[.679,.508,.12,.08]},
 tadpole:{closed:[.508,.62,.125,.10],open:[.477,.68,.125,.10]}
});
export function mouthMix(now,started=0,seed=0,enabled=true,speech=null) {
 if(!enabled||speech?.duration===0)return 0;
 const elapsed=Math.max(0,now-started);
 if(speech&&(elapsed>speech.duration||speech.pauses.some(t=>elapsed>=t&&elapsed<t+220)))return 0;
 const phase=elapsed/155+(seed%7)*.4;
 // Brief pauses between short syllable groups, without moving the torso.
 if(elapsed%1600>1150)return 0;
 return Math.pow(Math.max(0,Math.sin(phase)),1.3)*Math.min(1,elapsed/120);
}
export function mouthGeometry(info,img,frame,pixels) {
 const spec=MOUTHS[info.id],cw=img.naturalWidth/4,ch=img.naturalHeight/info.rows;
 const [cx,cy,w,h]=spec.closed,[ox,oy,ow,oh]=spec.open;
 const scale=Math.min(pixels/frame.w,pixels*.9/frame.h);
 return {source:{x:(ox-ow/2)*cw,y:ch+(oy-oh/2)*ch,w:ow*cw,h:oh*ch},
 target:{x:(pixels-frame.w*scale)/2+((cx-w/2)*cw-frame.x)*scale,y:pixels-frame.h*scale+((cy-h/2)*ch-frame.y)*scale,w:w*cw*scale,h:h*ch*scale}};
}

export function speechPattern(message,emoticon=false){if(emoticon)return {duration:0,pauses:[]};const chars=graphemes(message||'');return {duration:Math.min(9000,Math.max(550,chars.length*95)),pauses:chars.flatMap((ch,i)=>/[,.!?，。！？\n]/u.test(ch)?[(i+1)*95]:[])};}
