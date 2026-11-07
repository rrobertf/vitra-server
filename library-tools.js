/* Pure library helpers: local listening periods and portable playlist files. */
(()=>{
const day=d=>[d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');
const identity=t=>t.appleId?'apple:'+t.appleId:t.vid?'yt:'+t.vid:'';
function bounds(kind,offset=0,now=new Date()){
 const start=new Date(now.getFullYear(),now.getMonth(),now.getDate());
 if(kind==='week'){start.setDate(start.getDate()-((start.getDay()+6)%7)+offset*7);}else if(kind==='month'){start.setDate(1);start.setMonth(start.getMonth()+offset);}else{start.setMonth(0,1);start.setFullYear(start.getFullYear()+offset);}
 const end=new Date(start);if(kind==='week')end.setDate(end.getDate()+7);else if(kind==='month')end.setMonth(end.getMonth()+1);else end.setFullYear(end.getFullYear()+1);
 return {start,end,from:day(start),until:day(end)};
}
function add(log,track,seconds,plays=0,at=new Date()){
 const id=identity(track);if(!id||!Number.isFinite(seconds)||seconds<0||seconds>60)return;
 const bucket=log[day(at)]||(log[day(at)]={});const value=bucket[id]||(bucket[id]={track:{t:track.t,a:track.a,art:track.art,vid:track.vid,appleId:track.appleId,d:track.d},seconds:0,plays:0});
 value.seconds+=seconds;value.plays+=plays;
}
function summary(log,kind,offset=0,now=new Date()){
 const range=bounds(kind,offset,now),tracks=new Map(),artists=new Map();let seconds=0,plays=0;
 for(const [date,bucket] of Object.entries(log||{})){if(date<range.from||date>=range.until||!bucket||typeof bucket!=='object')continue;for(const [id,v] of Object.entries(bucket)){if(!v?.track||!Number.isFinite(v.seconds)||v.seconds<0)continue;const t=tracks.get(id)||{...v.track,id,seconds:0,plays:0};t.seconds+=v.seconds;t.plays+=Number(v.plays)||0;tracks.set(id,t);const artist=String(v.track.a||'Artista'),a=artists.get(artist)||{name:artist,art:v.track.art,seconds:0,plays:0};a.seconds+=v.seconds;a.plays+=Number(v.plays)||0;artists.set(artist,a);seconds+=v.seconds;plays+=Number(v.plays)||0;}}
 const order=(a,b)=>b.seconds-a.seconds||b.plays-a.plays;return {...range,seconds,plays,tracks:[...tracks.values()].sort(order),artists:[...artists.values()].sort(order)};
}
const clean=v=>String(v??'').replace(/[<>&"']/g,' ').trim().slice(0,250);
const header=v=>String(v).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
function csv(text){const first=text.split(/\r?\n/)[0],delimiter=first.includes('\t')?'\t':(first.split(';').length>first.split(',').length?';':',');let rows=[],row=[],cell='',quoted=false;for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){cell+='"';i++;}else quoted=!quoted;}else if(c===delimiter&&!quoted){row.push(cell);cell='';}else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(cell);if(row.some(v=>v.trim()))rows.push(row);row=[];cell='';}else cell+=c;}if(quoted)throw Error('Hay una comilla sin cerrar en el archivo.');row.push(cell);if(row.some(v=>v.trim()))rows.push(row);return rows;}
function plist(node){if(!node)return null;const children=[...node.children];if(node.tagName==='dict'){const value=Object.create(null);for(let i=0;i<children.length;i+=2){const k=children[i].textContent;if(!['__proto__','constructor','prototype'].includes(k))value[k]=plist(children[i+1]);}return value;}if(node.tagName==='array')return children.map(plist);if(node.tagName==='integer'||node.tagName==='real')return Number(node.textContent);return node.textContent;}
function parse(text,filename='Playlist'){
 let title=filename.replace(/\.[^.]+$/,''),tracks=[],warnings=[];text=text.replace(/^\uFEFF/,'');
 if(text.trimStart().startsWith('<')){if(/<!ENTITY/i.test(text))throw Error('El XML contiene entidades no permitidas.');const xml=new DOMParser().parseFromString(text,'application/xml');if(xml.querySelector('parsererror'))throw Error('El XML no es válido.');const root=plist(xml.querySelector('plist > dict'));if(!root?.Tracks)throw Error('Elige un XML de playlist exportado por Apple Music.');const playlists=(root.Playlists||[]).filter(p=>Array.isArray(p['Playlist Items']));if(playlists.length>1)throw Error('El archivo contiene varias playlists. Exporta una sola playlist de Apple Music.');const list=playlists[0];title=list?.Name||title;const refs=list?list['Playlist Items'].map(p=>String(p['Track ID'])):Object.keys(root.Tracks);tracks=refs.map(id=>root.Tracks[id]).filter(Boolean).map(t=>({t:t.Name,a:t.Artist}));
 }else if(text.trimStart().startsWith('{')){const value=JSON.parse(text);title=value.name||title;const entries=value.tracks?.items||value.tracks||value.items||value.playlists?.[0]?.items;if(!Array.isArray(entries))throw Error('El JSON no contiene una playlist compatible.');tracks=entries.map(x=>x.track||x.item||x).map(t=>({t:t.name||t.trackName||t.t,a:t.artistName||t.a||(t.artists||[]).map(a=>a.name).join(', ')}));
 }else{const rows=csv(text);if(!rows.length)throw Error('El archivo está vacío.');const columns=rows.shift().map(header),find=names=>columns.findIndex(h=>names.includes(h));const ti=find(['trackname','track','name','title','nombre','cancion','song','songname']),ai=find(['artistname','artistnames','artists','artist','artista','artistas']);if(ti<0||ai<0)throw Error('El archivo necesita columnas de canción y artista (Track Name y Artist Name, por ejemplo).');tracks=rows.map(r=>({t:r[ti],a:r[ai]}));}
 const total=tracks.length;tracks=tracks.filter(t=>typeof t.t==='string'&&typeof t.a==='string'&&t.t.trim()&&t.a.trim()).map(t=>({t:clean(t.t),a:clean(t.a)}));if(total!==tracks.length)warnings.push((total-tracks.length)+' filas sin canción o artista se omitieron.');
 if(!tracks.length)throw Error('No se encontraron canciones con artista.');if(tracks.length>1000)throw Error('Importa como máximo 1.000 canciones por archivo.');return {title:clean(title)||'Playlist importada',tracks,warnings};
}
window.VitraLibraryTools={day,identity,bounds,add,summary,parse};
})();
