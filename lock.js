
(()=>{
const root=document.getElementById('vitra-lockscreen'),phone=root.querySelector('.lock-phone');
const tracks=window.VitraCatalog;
let state={track:0,playing:true,position:32,compact:false,favorite:false},revision=0;const saved=null;if(saved&&tracks[saved.track])Object.assign(state,saved);
const time=n=>Math.floor(n/60)+':'+String(Math.floor(n%60)).padStart(2,'0');
function save(){}
function drawIcon(c,kind){const ctx=c.getContext('2d');ctx.clearRect(0,0,72,72);ctx.save();ctx.scale(3,3);ctx.fillStyle='#f5f3ee';if(kind==='favorite'){
ctx.strokeStyle=getComputedStyle(c).color;ctx.fillStyle=getComputedStyle(c).color;ctx.lineWidth=1.8;ctx.lineJoin='round';ctx.lineCap='round';ctx.beginPath();
for(let i=0;i<10;i++){const angle=-Math.PI/2+i*Math.PI/5,r=i%2===0?10.5:4.65,x=12+Math.cos(angle)*r,y=12+Math.sin(angle)*r;i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);}ctx.closePath();if(state.favorite)ctx.fill();else ctx.stroke();
}else if(kind==='audio-output'){
ctx.strokeStyle=getComputedStyle(c).color;ctx.lineWidth=1.45;ctx.lineCap='round';ctx.lineJoin='round';
for(const radius of[3.3,6.4,9.5]){ctx.beginPath();ctx.arc(12,10.4,radius,Math.PI*.73,Math.PI*2.27);ctx.stroke();}
ctx.beginPath();ctx.moveTo(12,14.4);ctx.lineTo(5.8,22.6);ctx.lineTo(18.2,22.6);ctx.closePath();ctx.stroke();
}else if(kind==='pause'){for(const x of[5,13.5]){ctx.beginPath();ctx.roundRect(x,3,5.5,18,1.2);ctx.fill();}}else if(kind==='play'){ctx.fill(new Path2D('M7 3 Q5 2 5 5 L5 19 Q5 22 8 20 L21 14 Q24 12 21 10 Z'));}else{if(kind==='next'){ctx.translate(24,0);ctx.scale(-1,1);}ctx.fill(new Path2D('M11 5 Q11 3 9 4 L1 10 Q-1 12 1 14 L9 20 Q11 21 11 19 Z M23 5 Q23 3 21 4 L13 10 Q11 12 13 14 L21 20 Q23 21 23 19 Z'));}ctx.restore();}
function timeline(){const t=tracks[state.track],input=root.querySelector('input');input.max=window.VitraAudio.audio.duration||Number(t.d.split(':')[0])*60+Number(t.d.split(':')[1]);input.value=state.position;input.style.setProperty('--position',state.position/Number(input.max)*100+'%');root.querySelector('.elapsed').textContent=time(state.position);root.querySelector('.remaining').textContent='−'+time(Math.max(0,Number(input.max)-state.position));}
function render(){phone.classList.toggle('is-playing',!!state.playing);const t=tracks[state.track];root.querySelector('h2').textContent=t.t;root.querySelector('.metadata p').textContent=t.a;root.querySelector('.output-title').textContent=t.t;root.querySelector('.output-artist').textContent=t.a;root.querySelector('.output-art').setAttribute('aria-label','Portada de '+t.t);phone.classList.toggle('compact',state.compact);root.querySelector('.favorite').setAttribute('aria-pressed',String(!!state.favorite));root.querySelectorAll('.cover,.output-art').forEach(c=>{c.style.backgroundImage='url("'+tracks[state.track].art+'")';c.style.backgroundSize='100% 100%';c.style.backgroundPosition='center';});root.querySelectorAll('canvas').forEach(c=>drawIcon(c,c.closest('.play')?(state.playing?'pause':'play'):c.dataset.icon));root.querySelector('.play').setAttribute('aria-label',state.playing?'Pausar':'Reproducir');timeline();}
root.querySelectorAll('.cover').forEach(c=>c.onclick=()=>{state.compact=!state.compact;render();save();});

root.querySelector('.favorite').onclick=()=>{state.favorite=!state.favorite;root.querySelector('.favorite').setAttribute('aria-pressed',String(state.favorite));render();save();};
root.querySelector('.wallpaper-picker').onclick=()=>root.querySelector('.wallpaper-file').click();
root.querySelector('.wallpaper-file').onchange=e=>{const file=e.target.files[0];if(!file||!file.type.startsWith('image/'))return;const image=new Image(),url=URL.createObjectURL(file);image.onload=()=>{root.querySelector('.wallpaper').style.background='linear-gradient(#0002,#0002),url("'+url+'") center/cover';};image.onerror=()=>URL.revokeObjectURL(url);image.src=url;};

const outputOverlay=root.querySelector('.audio-overlay'),outputButton=root.querySelector('.output');
function setOutputOpen(open){outputOverlay.hidden=!open;outputButton.setAttribute('aria-expanded',String(open));for(const child of phone.children){if(child!==outputOverlay)child.inert=open;}if(open)root.querySelector('.audio-close').focus();else outputButton.focus();}
outputButton.setAttribute('aria-haspopup','dialog');outputButton.setAttribute('aria-expanded','false');
outputButton.onclick=()=>{if(!window.VitraAudio.requestAirPlay())setOutputOpen(outputOverlay.hidden);};
root.querySelector('.audio-backdrop').onclick=()=>setOutputOpen(false);
root.querySelector('.audio-close').onclick=()=>setOutputOpen(false);
root.querySelectorAll('.audio-device').forEach(button=>button.onclick=()=>setOutputOpen(false));
function updateDevices(){root.querySelectorAll('.audio-device').forEach(button=>{const selected=button.dataset.device===(state.output||'phone');button.classList.toggle('selected',selected);button.setAttribute('aria-pressed',String(selected));});}
updateDevices();
root.addEventListener('keydown',event=>{if(outputOverlay.hidden)return;if(event.key==='Escape'){event.preventDefault();setOutputOpen(false);}if(event.key==='Tab'){const buttons=[...root.querySelectorAll('.audio-destination button')],first=buttons[0],last=buttons[buttons.length-1];if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}});
root.querySelectorAll('[data-action]').forEach(b=>b.onclick=()=>{if(b.dataset.action==='play')window.VitraMobile.toggle();else window.VitraMobile.advance(b.dataset.action==='next'?1:-1);});root.querySelector('input[type=range]').oninput=e=>window.VitraAudio.seek(Number(e.target.value));
const realPlayer=window.VitraAudio;
state.playing=!realPlayer.audio.paused;state.position=realPlayer.audio.currentTime;state.track=(realPlayer.currentIndex>=0?realPlayer.currentIndex:window.VitraMobile.state.song);state.favorite=window.VitraMobile.state.favorites.includes(state.track);
function trackTime(index){const d=tracks[index].d.split(':').map(Number);return d[0]*60+d[1];}
realPlayer.on('track',event=>{state.track=event.index;state.position=0;state.playing=false;state.favorite=window.VitraMobile.state.favorites.includes(state.track);render();});
realPlayer.on('state',event=>{if(event.index<0)return;state.track=event.index;state.playing=event.playing;state.position=realPlayer.audio.currentTime;render();});
realPlayer.on('position',event=>{if(event.index<0)return;state.track=event.index;state.position=event.position;timeline();});
realPlayer.on('error',()=>{state.playing=false;render();});
realPlayer.on('levels',event=>{root.querySelectorAll('.equalizer').forEach(wave=>{wave.dataset.rms=event.rms.toFixed(6);wave.querySelectorAll('b').forEach((bar,i)=>bar.style.transform='scaleY('+(.08+event.values[i]*.92).toFixed(3)+')');});});
const returnButton=document.createElement('button');returnButton.className='return-app';returnButton.textContent='Volver a Vitra';phone.appendChild(returnButton);
window.VitraShowLock=()=>{document.getElementById('vitra-iphone').hidden=true;root.hidden=false;state.track=(realPlayer.currentIndex>=0?realPlayer.currentIndex:window.VitraMobile.state.song);state.playing=!realPlayer.audio.paused;state.position=realPlayer.audio.currentTime;state.favorite=window.VitraMobile.state.favorites.includes(state.track);render();};
returnButton.onclick=()=>{root.hidden=true;document.getElementById('vitra-iphone').hidden=false;};
root.querySelector('.favorite').onclick=()=>{window.VitraMobile.favorite(state.track);state.favorite=window.VitraMobile.state.favorites.includes(state.track);render();};

window.addEventListener('openai:set_globals',e=>{const s=e.detail?.globals?.widgetState?.privateContent;if(s&&tracks[s.track]&&s.revision>revision){revision=s.revision;Object.assign(state,s);render();}});
render();
})();
