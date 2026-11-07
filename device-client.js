// Device-local library. Never read another account's cloud or legacy browser state.
const DEVICE_DB='vitra-device-library-v1';
const openDB=new Promise((resolve,reject)=>{const r=indexedDB.open(DEVICE_DB,1);r.onupgradeneeded=()=>r.result.createObjectStore('library');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
async function record(mode,value){const db=await openDB;return new Promise((resolve,reject)=>{const tx=db.transaction('library',mode),store=tx.objectStore('library'),r=value===undefined?store.get('current'):store.put(value,'current');let result;r.onsuccess=()=>result=r.result;tx.oncomplete=()=>resolve(result);tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);});}
const empty=()=>({state:{playlists:[],playlistData:{},favorites:[],history:[],searchHistory:[]},covers:{}});
function validateBackup(file){
 if(!file||file.app!=='Vitra'||file.format!==1||!file.data||typeof file.data!=='object')throw Error('Esta copia no tiene un formato compatible con Vitra.');
 const data=file.data,s=data.state;
 if(!s||typeof s!=='object'||Array.isArray(s)||!Array.isArray(s.playlists)||!Array.isArray(s.favorites))throw Error('La biblioteca de esta copia no es válida.');
 for(const k of ['playlists','favorites','history','searchHistory','catalog','recentChoices','playNext'])if(s[k]!==undefined&&(!Array.isArray(s[k])||s[k].length>50000))throw Error('La copia contiene una lista no válida.');
 if(!s.playlists.every(v=>typeof v==='string')||!s.favorites.every(Number.isInteger))throw Error('Las playlists o favoritas no son válidas.');
 if(s.listeningLog!==undefined){if(!s.listeningLog||typeof s.listeningLog!=='object'||Array.isArray(s.listeningLog))throw Error('El resumen musical no es válido.');for(const [date,bucket] of Object.entries(s.listeningLog)){if(!/^\d{4}-\d{2}-\d{2}$/.test(date)||!bucket||typeof bucket!=='object'||Array.isArray(bucket))throw Error('El resumen musical contiene una fecha no válida.');for(const value of Object.values(bucket))if(!value||!value.track||typeof value.track.t!=='string'||typeof value.track.a!=='string'||!Number.isFinite(value.seconds)||value.seconds<0||!Number.isFinite(value.plays)||value.plays<0)throw Error('El resumen musical contiene una escucha no válida.');}}
 for(const k of ['playlistData','listenCounts','listenSeconds','skips'])if(s[k]!==undefined&&(!s[k]||typeof s[k]!=='object'||Array.isArray(s[k])))throw Error('La copia contiene preferencias no válidas.');
 for(const p of Object.values(s.playlistData||{}))if(!p||!Array.isArray(p.tracks)||!p.tracks.every(Number.isInteger))throw Error('Una playlist no es válida.');
 for(const t of s.catalog||[])if(!t||typeof t.t!=='string'||typeof t.a!=='string'||typeof t.d!=='string')throw Error('Una canción no es válida.');
 let nodes=0;
 function visit(v,depth=0){if(++nodes>500000||depth>20)throw Error('La copia es demasiado compleja.');if(typeof v==='string'&&(/[<>]|javascript:|data:text\/html/i.test(v)))throw Error('La copia contiene contenido no permitido.');if(v&&typeof v==='object')for(const [k,x] of Object.entries(v)){if(['__proto__','prototype','constructor'].includes(k))throw Error('La copia contiene propiedades no válidas.');visit(x,depth+1);}}
 visit(data);
 if(data.covers!==undefined&&(!data.covers||typeof data.covers!=='object'||Array.isArray(data.covers)))throw Error('Las portadas no son válidas.');
 for(const [k,v] of Object.entries(data.covers||{}))if(!/^\d+$/.test(k)||typeof v!=='string'||!/^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$/.test(v))throw Error('Una portada personalizada no es válida.');
 return {state:{...s,page:'home',playing:false,lyrics:false,revision:(Number(s.revision)||0)+1},covers:data.covers||{}};
}
const status=document.createElement('p');status.setAttribute('role','status');status.style.cssText='position:fixed;top:12px;left:50%;transform:translateX(-50%);z-index:99999;background:#252a29;color:white;padding:12px 18px;border-radius:18px;max-width:90%;font:14px system-ui';status.hidden=true;document.body.append(status);
function announce(text){status.textContent=text;status.hidden=false;}
try{
 let envelope=await record('readonly');
 if(!envelope){envelope={id:crypto.randomUUID(),data:empty()};await record('readwrite',envelope);}
 let data=envelope.data,queue=Promise.resolve(),restoring=false;
 function save(){if(restoring)return Promise.resolve();const snapshot=structuredClone({id:envelope.id,data});const job=queue.then(()=>record('readwrite',snapshot));queue=job.catch(()=>{});return job.catch(error=>{announce('No se pudo guardar en este dispositivo. Revisa el espacio disponible y crea una copia.');throw error;});}
 window.VitraAccount={user:{id:envelope.id,name:'En este dispositivo',email:''},coversJSON:()=>JSON.stringify(data.covers||{}),saveCovers:covers=>{data={...data,covers};save().catch(()=>{});}};
 window.openai={widgetState:{privateContent:data.state},setWidgetState:async value=>{data={...data,state:structuredClone(value.privateContent)};await save();}};
 const input=document.createElement('input');input.type='file';input.accept='.json,application/json';input.hidden=true;document.body.append(input);
 input.onchange=async()=>{const f=input.files[0];input.value='';if(!f)return;try{if(f.size>20*1024*1024)throw Error('Elige una copia de menos de 20 MB.');const imported=validateBackup(JSON.parse(await f.text()));if(!confirm('Restaurar esta copia sustituirá la biblioteca y las preferencias actuales de este dispositivo. ¿Continuar?'))return;restoring=true;window.VitraAudio?.audio.pause();await queue;await record('readwrite',{id:envelope.id,data:imported});location.reload();}catch(error){restoring=false;announce(error instanceof SyntaxError?'El archivo no es una copia JSON válida.':error.message);}};
 document.addEventListener('click',async event=>{const b=event.target.closest('[data-device-backup],[data-device-restore]');if(!b)return;if(b.hasAttribute('data-device-restore')){input.click();return;}b.disabled=true;try{await queue;const copy={app:'Vitra',format:1,createdAt:new Date().toISOString(),data:structuredClone(data)};const blob=new Blob([JSON.stringify(copy,null,2)],{type:'application/json'}),name='Vitra-copia-'+new Date().toISOString().slice(0,10)+'.json',file=new File([blob],name,{type:'application/json'});if(navigator.canShare?.({files:[file]})){await navigator.share({files:[file],title:'Copia de seguridad de Vitra'});}else{const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);}announce('Copia preparada. Guárdala en Archivos o en un lugar seguro.');}catch(error){if(error.name!=='AbortError')announce('No se pudo crear la copia. Vuelve a intentarlo.');}finally{b.disabled=false;}});
 if(navigator.storage?.persist)navigator.storage.persist().catch(()=>{});
 for(const src of ['/library-tools.js','/lucide.js','/offline.js','/audio.js','/app.js','/lock.js'])await new Promise((resolve,reject)=>{const script=document.createElement('script');script.src=src;script.onload=resolve;script.onerror=reject;document.body.append(script);});
 window.finishVitraWelcome?.();
}catch(error){window.finishVitraWelcome?.();announce('Vitra necesita almacenamiento local para abrir tu biblioteca. Permite el almacenamiento del sitio y vuelve a intentarlo.');}
