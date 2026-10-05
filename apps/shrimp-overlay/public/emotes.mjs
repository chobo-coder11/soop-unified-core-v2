const HOSTS = new Set(['ogqmarket.img.sooplive.com', 'ogq-sticker-global-cdn-z01.sooplive.com']);
export function safeEmoteUrl(value) {
  if (typeof value !== 'string' || value.length > 2048) return null;
  try { const u = new URL(value); return u.protocol === 'https:' && HOSTS.has(u.hostname) && !u.username && !u.password && !u.port && /^\/sticker\/[a-zA-Z0-9]{4,32}\/\d{1,5}(?:_160)?\.(?:png|webp|gif)$/.test(u.pathname) && !u.search && !u.hash ? u.href : null; } catch { return null; }
}
export function ogqEmote(payload = {}) {
  const groupId = String(payload.groupId ?? '').trim(), subId = String(payload.subId ?? '').trim();
  if (!/^[a-zA-Z0-9]{4,32}$/.test(groupId) || !/^\d{1,5}$/.test(subId)) return null;
  // Official OGQ market publishes animated .webp and static .png for the same item.
  const base = `https://ogqmarket.img.sooplive.com/sticker/${groupId}/${subId}`;
  const explicit = safeEmoteUrl(payload.imageUrl || payload.emoticonUrl);
  return { kind: 'ogq', groupId, subId, label: 'OGQ 이모티콘', sources: [...new Set([explicit, `${base}.webp`, `${base}.png`].filter(Boolean))] };
}
// Keep img elements alive while their bubble is alive. Reassigning src every
// animation frame would restart animated WebP/GIF playback.
export class EmoteLayer {
  constructor(root, { makeImage = () => new Image(), now = () => Date.now(), retryMs=15000 } = {}) { this.now=now;this.retryMs=retryMs;this.failures=new Map();this.root = root; this.makeImage = makeImage; this.assets = new Map(); this.nodes = new Map(); }
  asset(emote) {
    const sources = emote.sources?.map(safeEmoteUrl).filter(Boolean) || [];
    if (!sources.length) return { ready: true, failed: true };
    const key = sources.join('|'); let asset = this.assets.get(key); if(asset?.failed&&this.now()>=(asset.retryAt||0)&&asset.attempts<3){this.assets.delete(key);asset=null;}
    if (asset) { this.assets.delete(key); this.assets.set(key,asset); return asset; }
    const image = this.makeImage(); image.referrerPolicy = 'no-referrer'; image.decoding = 'async';
    asset = { ready: false, failed: false, image, src: '', index: 0, timer: null, attempts:(this.failures.get(key)||0)+1 };
    const finish = failed => { clearTimeout(asset.timer); asset.ready = true; asset.failed = failed;if(failed){asset.retryAt=this.now()+this.retryMs*asset.attempts;this.failures.set(key,asset.attempts);while(this.failures.size>64)this.failures.delete(this.failures.keys().next().value);}else this.failures.delete(key); if (!failed) asset.src = image.src; };
    const next = () => {
      clearTimeout(asset.timer); if (asset.ready) return;
      if (asset.index >= sources.length) { finish(true); return; }
      image.src = sources[asset.index++]; asset.timer = setTimeout(next, 3000);
    };
    image.onload = () => finish(false); image.onerror = next;
    this.assets.set(key, asset); next();
    while (this.assets.size > 64) { const oldest = this.assets.keys().next().value; const old = this.assets.get(oldest); clearTimeout(old.timer); old.image.onload = old.image.onerror = null; old.image.src = ''; this.assets.delete(oldest); }
    return asset;
  }
  draw(key, emote, { x, y, size, opacity }) {
    const asset = this.asset(emote); if (!asset.ready || asset.failed) return false;
    let node = this.nodes.get(key);
    if (!node || node.src !== asset.src) {
      node?.remove(); node = this.makeImage(); node.alt = emote.label; node.referrerPolicy = 'no-referrer'; node.decoding = 'async'; node.className = 'ogq-emote'; node.src = asset.src;
      this.nodes.set(key, node); this.root.append(node);
    }
    node.style.transform = `translate3d(${x}px,${y}px,0)`;
    node.style.width = node.style.height = `${size}px`; node.style.opacity = String(opacity); return true;
  }
  retain(keys) { for (const [key, node] of this.nodes) if (!keys.has(key)) { node.remove(); this.nodes.delete(key); } }
}
