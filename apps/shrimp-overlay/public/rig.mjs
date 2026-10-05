// Keep the face and torso on one model while animating the locomotion parts.
// Regions use normalized texture coordinates, not screen pixels.
export function walkingRegion(profile, direction = 1) {
  if (profile === 'hover') return { x:0, y:.12, w:1, h:.32 };
  if (profile === 'swim') return direction > 0
    ? { x:0, y:.15, w:.34, h:.85 }
    : { x:.66, y:.15, w:.34, h:.85 };
  if (profile === 'scoot') return { x:0, y:.72, w:1, h:.28 };
  return { x:0, y:.79, w:1, h:.21 };
}
export function gaitTiming(profile) {
  // One phase is a complete left/right stride. Longer strides prevent rapid
  // foot shuffling on small characters; fliers and swimmers have no footfall.
  return ({waddle:.29, hop:.38, hover:.46, swim:.48, heavy:.34, scoot:.36, sway:.32})[profile] || .31;
}
export function gaitDetail(profile, phase, strength = 1) {
  strength = Math.max(0,Math.min(1,strength));
  const wave=Math.sin(phase), contact=Math.abs(wave);
  const pair=({waddle:[1.2,.017],hop:[2.7,.011],hover:[.9,.009],swim:[.5,.017],heavy:[.65,.006],scoot:[.4,.012],sway:[.65,.017]})[profile] || [.8,.009];
  return { bob:(profile==='hover' ? -5-wave*pair[0] : -contact*pair[0])*strength,
    rotation:wave*pair[1]*strength };
}

export function jumpDetail(progress,height=24) {
  const p=Math.max(0,Math.min(1,progress));
  if(p<.16){const crouch=Math.sin(p/.16*Math.PI);return {bob:1.8*crouch,sx:1+.025*crouch,sy:1-.035*crouch};}
  if(p<.78){const flight=(p-.16)/.62;return {bob:-height*4*flight*(1-flight),sx:1,sy:1};}
  const settle=Math.sin((p-.78)/.22*Math.PI)*(1-(p-.78)/.22);
  return {bob:2*settle,sx:1+.028*settle,sy:1-.04*settle};
}
