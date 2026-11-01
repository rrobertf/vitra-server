/* Device-local downloads; audio is read directly from IndexedDB, never re-fetched. */
(()=>{
const key=t=>t.appleId?'apple:'+t.appleId:t.vid?'yt:'+t.vid:'';
const source=t=>t.appleId?'/api/apple-audio/'+encodeURIComponent(t.appleId):'/api/audio/'+encodeURIComponent(t.vid);
let db;const items=new Map(),pending=new Set();
const open=new Promise((resolve,reject)=>{const r=indexedDB.open('vitra-downloads',2);r.onupgradeneeded=()=>{const d=r.result;if(!d.objectStoreNames.contains('songs'))d.createObjectStore('songs',{keyPath:'id'});const meta=d.createObjectStore('metadata',{keyPath:'id'});const cursor=r.transaction.objectStore('songs').openCursor();cursor.onsuccess=()=>{const c=cursor.result;if(c){const {id,track,size,date}=c.value;meta.put({id,track,size,date});c.continue();}};};r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
async function request(mode,fn,store='songs'){const d=await open;return new Promise((resolve,reject)=>{const tx=d.transaction(store,mode),r=fn(tx.objectStore(store));let result;r.onsuccess=()=>result=r.result;tx.oncomplete=()=>resolve(result);tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);});}
async function writeRecord(record,remove){const d=await open;await new Promise((resolve,reject)=>{const tx=d.transaction(['songs','metadata'],'readwrite');for(const name of ['songs','metadata']){const store=tx.objectStore(name);if(remove)store.delete(record.id);else{const {id,track,size,date}=record;store.put(name==='songs'?record:{id,track,size,date});}}tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);});}
const changed=()=>window.dispatchEvent(new Event('vitra-downloads-changed'));
const ready=request('readonly',s=>s.getAll(),'metadata').then(records=>{for(const r of records)items.set(r.id,{track:r.track,size:r.size,date:r.date});changed();}).catch(()=>{});
window.VitraOffline={key,source,ready,items,pending,
 has:t=>items.has(key(t)),
 async url(t){await ready;const id=key(t);if(!items.has(id))return null;const r=await request('readonly',s=>s.get(id));return r?.blob?URL.createObjectURL(r.blob):null;},
 async download(t){await ready;const id=key(t);if(!id)throw Error('Esta canción no tiene una fuente de audio.');if(items.has(id)||pending.has(id))return;pending.add(id);changed();try{
  const response=await fetch(source(t));if(!response.ok){const detail=await response.json().catch(()=>({}));throw Error(detail.error||'No se pudo descargar la canción.');}
  const blob=await response.blob();if(!blob.size||!blob.type.startsWith('audio/'))throw Error('La descarga no contiene audio válido.');
  let track={...t};try{const cover=await fetch(t.art);if(cover.ok){const b=await cover.blob();track.offlineArt=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(b);});}}catch{}
  const record={id,track,blob,size:blob.size,date:Date.now()};await writeRecord(record,false);items.set(id,{track,size:record.size,date:record.date});
  if(navigator.storage?.persist)navigator.storage.persist().catch(()=>{});
 }finally{pending.delete(id);changed();}},
 async remove(t){const id=key(t);await writeRecord({id},true);items.delete(id);changed();}
};
if('serviceWorker'in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});
})();
