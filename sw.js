const CACHE='vitra-shell-v7-library';
const SHELL=['/library-tools.js','/','/index.html','/app.js','/device-client.js','/audio.js','/offline.js','/lock.js','/lucide.js','/icon.png','/manifest.webmanifest','/install.html','/icons/apple-touch-icon.png','/icons/icon-192.png','/icons/icon-512.png',...Array.from({length:6},(_,i)=>'/covers/'+i+'.webp')];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{const url=new URL(e.request.url);if(url.origin!==self.location.origin||e.request.method!=='GET')return;if(SHELL.includes(url.pathname))e.respondWith(fetch(e.request).then(r=>{if(r.ok){const copy=r.clone();caches.open(CACHE).then(c=>c.put(e.request,copy));}return r;}).catch(()=>caches.match(e.request).then(r=>r||(e.request.mode==='navigate'?caches.match('/'):Response.error()))));});

