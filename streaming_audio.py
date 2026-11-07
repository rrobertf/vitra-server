"""Progressive, bounded audio spool using the same compatible downloader as playback."""
import concurrent.futures,json,os,re,subprocess,sys,threading,time,uuid
class Download:
 def __init__(self,vid,path):self.vid=vid;self.path=path;self.size=None;self.written=0;self.ready=threading.Event();self.condition=threading.Condition();self.done=False;self.error=None
class StreamSources:
 def __init__(self,root,tools):self.root=root;self.tools=tools;self.cache=root/'cache';self.jobs={};self.lock=threading.Lock();self.pool=concurrent.futures.ThreadPoolExecutor(max_workers=2)
 def _run(self,job):
  metadata=job.path.with_suffix('.metadata.json');process=None
  try:
   env=os.environ.copy();env['PYTHONPATH']=str(self.tools)
   command=[sys.executable,'-m','yt_dlp','--ignore-config','-f','bestaudio[ext=m4a]','--no-playlist','--no-warnings','--no-progress','--quiet','--js-runtimes','node','--socket-timeout','10','--retries','0','--no-simulate','--print-to-file','before_dl:{"size":%(filesize)j}',str(metadata),'-o','-','https://music.youtube.com/watch?v='+job.vid]
   process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));deadline=time.monotonic()+45
   while not metadata.is_file():
    if process.poll() is not None:raise ValueError('No se pudo preparar el audio. Vuelve a intentarlo.')
    if time.monotonic()>deadline:raise ValueError('La fuente tardó demasiado en responder. Vuelve a intentarlo.')
    time.sleep(.03)
   try:info=json.loads(metadata.read_text(encoding='utf8'));size=info.get('size')
   except (OSError,ValueError):size=None
   job.size=int(size) if isinstance(size,(int,float)) and size>0 else None
   if job.size and job.size>128*1024**2:raise ValueError('Esta canción supera el tamaño permitido.')
   with job.path.open('wb') as file:
    job.ready.set();deadline=time.monotonic()+120
    while True:
     chunk=process.stdout.read(16384 if job.written==0 else 65536)
     if not chunk:break
     if time.monotonic()>deadline:raise ValueError('La fuente tardó demasiado en cargar el audio.')
     with job.condition:
      file.write(chunk);file.flush();job.written+=len(chunk);job.condition.notify_all()
   result=process.wait(timeout=10)
   if result or not job.written or (job.size and job.written!=job.size):raise ValueError('La fuente no completó un archivo de audio válido. Vuelve a intentarlo.')
   with job.condition:
    path=self.cache/(job.vid+'.m4a');job.path.replace(path);job.path=path;job.size=job.written;job.done=True;job.condition.notify_all()
   self.trim()
  except Exception as error:
   with job.condition:job.error=str(error) if isinstance(error,ValueError) else 'No se pudo cargar el audio. Vuelve a intentarlo.';job.done=True;job.condition.notify_all()
   job.path.unlink(missing_ok=True)
  finally:
   job.ready.set();metadata.unlink(missing_ok=True)
   if process:
    if process.poll() is None:process.kill()
    process.wait(timeout=10)
    if process.stdout:process.stdout.close()
 def resolve(self,vid,refresh=False):
  if not re.fullmatch(r'[A-Za-z0-9_-]{11}',vid):raise ValueError('Canción no válida.')
  with self.lock:
   path=self.cache/(vid+'.m4a');job=self.jobs.get(vid)
   if job and job.error and (refresh or time.monotonic()-getattr(job,'started',0)>20):self.jobs.pop(vid,None);job=None
   if not job:
    self.jobs={k:v for k,v in self.jobs.items() if not v.done}
    if path.is_file() and path.stat().st_size>0:
     job=Download(vid,path);job.size=job.written=path.stat().st_size;job.done=True;job.ready.set()
    else:
     if len(self.jobs)>=4:raise ValueError('Hay varias canciones preparándose. Vuelve a intentarlo en un momento.')
     job=Download(vid,self.cache/(vid+'.'+uuid.uuid4().hex+'.buffer'));job.started=time.monotonic();self.jobs[vid]=job;self.pool.submit(self._run,job)
  if not job.ready.wait(50):raise ValueError('El audio está tardando en prepararse. Vuelve a intentarlo.')
  if job.error:raise ValueError(job.error)
  return job
 def relay(self,handler,vid):
  if not re.fullmatch(r'[A-Za-z0-9_-]{11}',vid):raise ValueError('Canción no válida.')
  path=self.cache/(vid+'.m4a')
  if path.is_file() and path.stat().st_size>0:handler.send_file(path,True);return
  requested=handler.headers.get('Range')
  if requested and (len(requested)>80 or not re.fullmatch(r'bytes=(?:\d+-\d*|-\d+)',requested)):
   handler.send_response(416);handler.send_header('Content-Length','0');handler.end_headers();return
  job=self.resolve(vid)
  if requested and not job.size:
   with job.condition:job.condition.wait_for(lambda:job.done,timeout=120)
   if job.error or not job.done:raise ValueError(job.error or 'El audio todavía no está listo.')
  size=job.size;start=0;end=size-1 if size else None;partial=bool(requested and size)
  if partial:
   first,last=requested[6:].split('-')
   if first:start=int(first);end=min(int(last),size-1) if last else size-1
   else:start=max(0,size-int(last));end=size-1
   if start>=size or start>end or (not first and int(last)<=0):
    handler.send_response(416);handler.send_header('Content-Range','bytes */'+str(size));handler.send_header('Content-Length','0');handler.end_headers();return
  handler.send_response(206 if partial else 200);handler.send_header('Content-Type','audio/mp4');handler.send_header('Accept-Ranges','bytes');handler.send_header('Cache-Control','private,max-age=86400');handler.send_header('X-Content-Type-Options','nosniff')
  if size:handler.send_header('Content-Length',str(end-start+1))
  else:handler.send_header('Connection','close');handler.close_connection=True
  if partial:handler.send_header('Content-Range',f'bytes {start}-{end}/{size}')
  handler.end_headers()
  if handler.command=='HEAD':return
  position=start;deadline=time.monotonic()+120
  while end is None or position<=end:
   with job.condition:
    while job.written<=position and not job.done:
     if time.monotonic()>deadline:handler.close_connection=True;return
     job.condition.wait(timeout=1)
    if job.error:handler.close_connection=True;return
    available=job.written-position
    if available<=0:return
    amount=min(65536,available,(end-position+1) if end is not None else 65536)
    with job.path.open('rb') as file:file.seek(position);chunk=file.read(amount)
   if not chunk:handler.close_connection=True;return
   handler.wfile.write(chunk);handler.wfile.flush();position+=len(chunk)
 def trim(self):
  files=sorted(self.cache.glob('*.m4a'),key=lambda p:p.stat().st_mtime);total=sum(p.stat().st_size for p in files)
  for path in files:
   if total<=1024**3:break
   try:size=path.stat().st_size;path.unlink();total-=size
   except OSError:pass
