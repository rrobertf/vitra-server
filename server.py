"""Vitra mobile: local media gateway. No API keys or user cookies required."""
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlsplit,parse_qs
from pathlib import Path
import playlist_import,service_import
from lyrics_service import LyricsService
import home_feed
import device_auth as auth
import unicodedata,os
import argparse,concurrent.futures,datetime,json,mimetypes,re,subprocess,sys,threading,urllib.request

ROOT=Path(__file__).resolve().parent
CACHE=ROOT/'cache';CACHE.mkdir(exist_ok=True)
LYRICS=LyricsService(ROOT)
TOOLS=ROOT/'media-runtime' if (ROOT/'media-runtime').is_dir() else ROOT/'runtime'
sys.path.insert(0,str(TOOLS))
CATALOG=[
 {'vid':'jaHuI-x_EdI','t':'Enzaciao','a':'Clarent','d':'2:14'},
 {'vid':'dYjpqN6fYcQ','t':'BIENVENIDA','a':'Clarent','d':'1:46'},
 {'vid':'eGUAqH7XJEg','t':'Ojos Brujos','a':'Clarent','d':'4:10'},
 {'vid':'rdUHj6yQZ8A','t':'MI GATA','a':'Rowma','d':'3:08'},
 {'vid':'MIt-jqUOI-I','t':'Dime Baby','a':'Clarent','d':'3:10'},
 {'vid':'s67aTB3EjXc','t':'Lágrimas De Alegría','a':'Clarent','d':'3:13'}]
for i,t in enumerate(CATALOG):t.update(art=f'/covers/{i}.webp',c='#606066')
DOWNLOADS={};LOCK=threading.Lock();ART={};SEARCH_CACHE={}
try:
 stored_art=json.loads((CACHE/'artwork.json').read_text(encoding='utf8'))
 ART.update({k:v for k,v in stored_art.items() if re.fullmatch(r'(?:[A-Za-z0-9_-]{11}|MPRE[A-Za-z0-9_-]{1,100}|UC[A-Za-z0-9_-]{22}|AM[PBM]?[0-9]+)',k) and isinstance(v,str) and urlsplit(v).scheme=='https' and (urlsplit(v).hostname in ('yt3.googleusercontent.com','lh3.googleusercontent.com','i.ytimg.com') or re.fullmatch(r'is\d+-ssl\.mzstatic\.com',urlsplit(v).hostname or ''))})
except (OSError,ValueError,AttributeError):pass
POOL=concurrent.futures.ThreadPoolExecutor(max_workers=2)
def walk(x,key):
 if isinstance(x,dict):
  if key in x:yield x[key]
  for v in x.values():yield from walk(v,key)
 elif isinstance(x,list):
  for v in x:yield from walk(v,key)
def text(x):
 if not isinstance(x,dict):return ''
 return ''.join(r.get('text','') for r in x.get('runs',[])) or x.get('simpleText','')
def search(query,fresh=False):
 cached=SEARCH_CACHE.get(query.casefold())
 now=datetime.datetime.now(datetime.timezone.utc).timestamp()
 if not fresh and cached and now-cached[0]<(60 if cached[1] else 15):return cached[1]
 body={'context':{'client':{'clientName':'WEB_REMIX','clientVersion':'1.'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d')+'.01.00','hl':'en','gl':'US'}},'query':query,'params':'EgWKAQIIAWoMEA4QChADEAQQCRAF'}
 req=urllib.request.Request('https://music.youtube.com/youtubei/v1/search?prettyPrint=false',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','User-Agent':'Mozilla/5.0','Origin':'https://music.youtube.com'})
 with urllib.request.urlopen(req,timeout=20) as response:data=json.load(response)
 results=[];seen=set()
 for row in walk(data,'musicResponsiveListItemRenderer'):
  vid=row.get('playlistItemData',{}).get('videoId')
  if not vid:vid=next((v.get('videoId') for v in walk(row,'watchEndpoint') if v.get('videoId')),None)
  if not vid or not re.fullmatch(r'[\w-]{11}',vid) or vid in seen:continue
  cols=[text(v.get('musicResponsiveListItemFlexColumnRenderer',{}).get('text',{})) for v in row.get('flexColumns',[])]
  if not cols:continue
  durations=[text(v) for v in walk(row.get('fixedColumns',[]),'text')]+[part.strip() for col in cols for part in col.split('•')]
  duration=next((d for d in durations if re.fullmatch(r'\d+(?::\d{2}){1,2}',d)), '')
  artist=(cols[1].split('•')[0].strip() if len(cols)>1 else '').replace(' - Topic','')
  thumbs=list(walk(row.get('thumbnail',{}),'thumbnails'));url=thumbs[0][-1].get('url') if thumbs and thumbs[0] else None
  if url and urlsplit(url).hostname in ('yt3.googleusercontent.com','lh3.googleusercontent.com'):
   ART[vid]=re.sub(r'=w\d+-h\d+.*','=w720-h720-l85-rw',url)
  artist_refs=[]
  for col in row.get('flexColumns',[])[1:]:
   for run in col.get('musicResponsiveListItemFlexColumnRenderer',{}).get('text',{}).get('runs',[]):
    endpoint=run.get('navigationEndpoint',{}).get('browseEndpoint',{})
    if endpoint.get('browseEndpointContextSupportedConfigs',{}).get('browseEndpointContextMusicConfig',{}).get('pageType')=='MUSIC_PAGE_TYPE_ARTIST':artist_refs.append({'id':endpoint.get('browseId',''),'name':run.get('text','')})
  results.append({'artists':artist_refs,'vid':vid,'t':cols[0],'a':artist,'d':duration or '0:00','art':f'/api/art/{vid}' if vid in ART else '/icon.png','c':'#606066'})
  seen.add(vid)
 with LOCK:
  (CACHE/'artwork.json').write_text(json.dumps(ART),encoding='utf8')
 if len(SEARCH_CACHE)>100:SEARCH_CACHE.clear()
 SEARCH_CACHE[query.casefold()]=(now,results[:20]);return results[:20]

def search_recent_videos(query):
 # Read standard YouTube search metadata only when the Music index has no match.
 env=__import__('os').environ.copy();env['PYTHONPATH']=str(TOOLS)
 command=[sys.executable,'-m','yt_dlp','--flat-playlist','--dump-single-json','--no-warnings','--ignore-errors','--skip-download','--socket-timeout','12','--retries','0','ytsearch8:'+query]
 result=subprocess.run(command,capture_output=True,timeout=35,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 if not result.stdout:raise ValueError('No se pudo consultar YouTube. Comprueba la conexión y vuelve a intentarlo.')
 try:data=json.loads(result.stdout)
 except ValueError:raise ValueError('YouTube no devolvió resultados válidos.') from None
 tracks=[]
 for item in data.get('entries',[]):
  if not item or not re.fullmatch(r'[A-Za-z0-9_-]{11}',item.get('id','')):continue
  duration=round(item.get('duration') or 0);artist=item.get('channel') or item.get('uploader') or ''
  tracks.append({'vid':item['id'],'t':item.get('title',''),'a':artist,'durationSeconds':duration,'d':f'{duration//60}:{duration%60:02}','verified':item.get('channel_is_verified') is True,'isTopic':artist.endswith(' - Topic')})
 return tracks

ARTIST_CACHE={};ARTIST_PHOTOS={}
try:
 ARTIST_PHOTOS.update(json.loads((CACHE/'artist-photos.json').read_text(encoding='utf8')))
except (OSError,ValueError):pass

def normalized(value):
 return ''.join(c for c in unicodedata.normalize('NFKD',value.casefold()) if not unicodedata.combining(c))

def search_artists(query):
 key=normalized(query.strip())
 if key in ARTIST_CACHE:return ARTIST_CACHE[key]
 body={'context':{'client':{'clientName':'WEB_REMIX','clientVersion':'1.'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d')+'.01.00','hl':'en','gl':'US'}},'query':query,'params':'EgWKAQIgAWoKEAkQBRAKEAMQBA=='}
 req=urllib.request.Request('https://music.youtube.com/youtubei/v1/search?prettyPrint=false',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','User-Agent':'Mozilla/5.0','Origin':'https://music.youtube.com'})
 with urllib.request.urlopen(req,timeout=20) as response:data=json.load(response)
 results=[];seen=set()
 for row in walk(data,'musicResponsiveListItemRenderer'):
  endpoint=row.get('navigationEndpoint',{}).get('browseEndpoint',{})
  if endpoint.get('browseEndpointContextSupportedConfigs',{}).get('browseEndpointContextMusicConfig',{}).get('pageType')!='MUSIC_PAGE_TYPE_ARTIST':continue
  artist_id=endpoint.get('browseId','')
  columns=row.get('flexColumns',[])
  name=text(columns[0].get('musicResponsiveListItemFlexColumnRenderer',{}).get('text',{})) if columns else ''
  if not re.fullmatch(r'UC[A-Za-z0-9_-]{22}',artist_id) or artist_id in seen or key not in normalized(name):continue
  thumbs=list(walk(row.get('thumbnail',{}),'thumbnails'))
  url=thumbs[0][-1].get('url','') if thumbs and thumbs[0] else ''
  photo=''
  if urlsplit(url).scheme=='https' and urlsplit(url).hostname in ('yt3.googleusercontent.com','lh3.googleusercontent.com'):
   ARTIST_PHOTOS[artist_id]=re.sub(r'=w\d+-h\d+.*','=w720-h720-p-l90-rj',url)
   photo='/api/artist-art/'+artist_id
  results.append({'id':artist_id,'name':name,'photo':'/api/artist-portrait?name='+__import__('urllib.parse',fromlist=['quote']).quote(name)});seen.add(artist_id)
 with LOCK:(CACHE/'artist-photos.json').write_text(json.dumps(ARTIST_PHOTOS),encoding='utf8')
 if len(ARTIST_CACHE)>100:ARTIST_CACHE.clear()
 ARTIST_CACHE[key]=results[:10]
 return ARTIST_CACHE[key]

def catalog_id(index):
 if not 0<=index<len(CATALOG):raise ValueError('Canción no encontrada')
 track=CATALOG[index]
 if not track['vid']:
  choices=search(track['a']+' '+track['t'])
  match=next((t for t in choices if t['t'].casefold()==track['t'].casefold()),None)
  if not match:raise ValueError('No se encontró la canción exacta')
  track['vid']=match['vid']
 return track['vid']
def download(vid):
 path=CACHE/(vid+'.m4a')
 if path.is_file() and path.stat().st_size>0:return path
 command=[sys.executable,'-m','yt_dlp','-f','bestaudio[ext=m4a]','--no-playlist','--no-warnings','--no-progress','--quiet','--js-runtimes','node','--socket-timeout','15','--retries','1','-o',str(CACHE/(vid+'.%(ext)s')),f'https://music.youtube.com/watch?v={vid}']
 env=__import__('os').environ.copy();env['PYTHONPATH']=str(TOOLS)
 result=subprocess.run(command,capture_output=True,timeout=90,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 if result.returncode or not path.exists():raise ValueError('No se pudo cargar esta canción de YouTube. Prueba otra o vuelve a intentarlo.')
 # Bound only this application's completed cache. Never touch the desktop app's cache.
 files=sorted(CACHE.glob('*.m4a'),key=lambda f:f.stat().st_mtime);total=sum(f.stat().st_size for f in files)
 for file in files:
  if total<=1024**3:break
  if file==path:continue
  try:size=file.stat().st_size;file.unlink();total-=size
  except OSError:pass
 return path
def media(vid):
 if not re.fullmatch(r'[A-Za-z0-9_-]{11}',vid):raise ValueError('Identificador no válido')
 with LOCK:
  if vid not in DOWNLOADS or (DOWNLOADS[vid].done() and DOWNLOADS[vid].exception()):DOWNLOADS[vid]=POOL.submit(download,vid)
  future=DOWNLOADS[vid]
 try:return future.result(timeout=95)
 finally:
  with LOCK:
   if future.done() and DOWNLOADS.get(vid) is future:DOWNLOADS.pop(vid,None)
def byte_range(header,size):
 if not header:return 0,size-1,False
 m=re.fullmatch(r'bytes=(\d*)-(\d*)',header)
 if not m or not any(m.groups()):raise ValueError('Range inválido')
 a,b=m.groups()
 if not a:
  if int(b)<=0:raise ValueError('Range inválido')
  start=max(0,size-int(b));end=size-1
 else:start=int(a);end=min(int(b),size-1) if b else size-1
 if start>=size or start>end:raise ValueError('Range fuera del archivo')
 return start,end,True
from streaming_audio import StreamSources
STREAM_SOURCES=StreamSources(ROOT,TOOLS)
AUDIO_PREP_POOL=concurrent.futures.ThreadPoolExecutor(max_workers=1);AUDIO_PREP_PENDING=set()
def prepare_audio(data):
 key='apple:'+str(data['appleId']) if data.get('appleId') else 'yt:'+str(data.get('vid',''))
 with LOCK:
  if key in AUDIO_PREP_PENDING or AUDIO_PREP_PENDING:return False
  AUDIO_PREP_PENDING.add(key)
 def prepare():
  try:
   vid=APPLE_CATALOGUE.resolve_audio(str(data['appleId'])) if data.get('appleId') else data['vid']
   if not (CACHE/(vid+'.m4a')).is_file():STREAM_SOURCES.resolve(vid)
  except Exception:pass
  finally:
   with LOCK:AUDIO_PREP_PENDING.discard(key)
 AUDIO_PREP_POOL.submit(prepare);return True
from artist_catalogue import ArtistCatalogue
ARTIST_CATALOGUE=ArtistCatalogue(ROOT,ART,walk,text)
from apple_catalogue import AppleCatalogue
APPLE_CATALOGUE=AppleCatalogue(ROOT,ART,search,search_fresh=lambda q:search(q,fresh=True),fallback_search=search_recent_videos)
from recommendations import Recommender
RECOMMENDER=Recommender(APPLE_CATALOGUE)
HOME_FEED=home_feed.HomeFeed(APPLE_CATALOGUE,RECOMMENDER,ROOT)

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send_json(self,status,data):
  content=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);
  if getattr(self,'account_cookie',None):self.send_header('Set-Cookie',self.account_cookie)
  self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','no-store');self.end_headers()
  if self.command!='HEAD':self.wfile.write(content)
 def do_POST(self):
  try:self.account_POST()
  except (BrokenPipeError,ConnectionResetError):pass
  except Exception as error:
   (ROOT/'data'/'account-diagnostic.json').write_text(json.dumps({'type':type(error).__name__,'sqlstate':getattr(error,'sqlstate',None)}),encoding='utf8')
   self.send_json(503,{'error':'El servidor no pudo acceder a tu cuenta. Inténtalo de nuevo.'})
 def account_POST(self):
  if auth.handle(self):return
  if not auth.user(self):self.send_json(401,{'error':'Inicia sesión para continuar.'});return
  if urlsplit(self.path).path=='/api/lyrics':
   if self.headers.get_content_type()!='application/json' or self.headers.get('Sec-Fetch-Site')=='cross-site' or (self.headers.get('Origin') and urlsplit(self.headers['Origin']).netloc!=self.headers.get('Host')):
    self.send_json(403,{'error':'Solicitud no permitida.'});return
   try:
    size=int(self.headers.get('Content-Length','0'))
    if not 0<size<=4096:raise ValueError('Solicitud no válida.')
    payload=json.loads(self.rfile.read(size))
    if not isinstance(payload,dict):raise ValueError('Solicitud no válida.')
    self.send_json(200,LYRICS.get(payload))
   except ValueError as error:self.send_json(400,{'error':str(error)[:180]})
   except Exception:self.send_json(502,{'error':'No se pudieron consultar las letras. Vuelve a intentarlo.'})
   return
  if urlsplit(self.path).path=='/api/audio-prepare':
   if self.headers.get_content_type()!='application/json' or self.headers.get('Sec-Fetch-Site')=='cross-site' or (self.headers.get('Origin') and urlsplit(self.headers['Origin']).netloc!=self.headers.get('Host')):
    self.send_json(403,{'error':'Solicitud no permitida.'});return
   try:
    size=int(self.headers.get('Content-Length','0'))
    if not 0<size<=512:raise ValueError()
    data=json.loads(self.rfile.read(size))
    if not isinstance(data,dict):raise ValueError()
    if data.get('appleId'):
     if not isinstance(data['appleId'],str) or not data['appleId'].isdigit() or data['appleId'] not in APPLE_CATALOGUE.songs:raise ValueError()
    elif not isinstance(data.get('vid'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{11}',data['vid']):raise ValueError()
    self.send_json(202,{'preparing':prepare_audio(data)})
   except (ValueError,TypeError,KeyError):self.send_json(400,{'error':'Canción no válida.'})
   return
  if urlsplit(self.path).path in ('/api/import/resolve','/api/import/service'):
   if self.headers.get('Sec-Fetch-Site')=='cross-site' or self.headers.get_content_type()!='application/json' or (self.headers.get('Origin') and urlsplit(self.headers['Origin']).netloc!=self.headers.get('Host')):
    self.send_json(403,{'error':'Solicitud no permitida.'});return
   try:
    size=int(self.headers.get('Content-Length','0'))
    if not 0<size<=65536:raise ValueError('Solicitud demasiado grande.')
    payload=json.loads(self.rfile.read(size))
    if not isinstance(payload,dict):raise ValueError('Solicitud no válida.')
    result=playlist_import.resolve(payload,APPLE_CATALOGUE) if urlsplit(self.path).path.endswith('/resolve') else service_import.handle(payload)
    self.send_json(200,result)
   except ValueError as error:self.send_json(400,{'error':str(error)[:240]})
   except (TypeError,KeyError):self.send_json(400,{'error':'No se pudo leer la playlist. Revisa su formato.'})
   except Exception:self.send_json(502,{'error':'No se pudo consultar el servicio. Inténtalo de nuevo más tarde.'})
   return
  if urlsplit(self.path).path in ('/api/home-personal','/api/new-releases'):
   try:
    size=int(self.headers.get('Content-Length','0'))
    if not 0<size<=65536 or self.headers.get('Sec-Fetch-Site')=='cross-site':raise ValueError('Solicitud no válida')
    payload=json.loads(self.rfile.read(size))
    if not isinstance(payload,dict):raise ValueError('Solicitud no válida')
    self.send_json(200,HOME_FEED.new_releases(payload) if urlsplit(self.path).path=='/api/new-releases' else HOME_FEED.mixes(payload,auth.user(self)['id']))
   except Exception as error:self.send_json(502,{'error':str(error)[:180]})
   return
  if urlsplit(self.path).path!='/api/recommendations':self.send_json(404,{'error':'No encontrado'});return
  if self.headers.get('Sec-Fetch-Site')=='cross-site':self.send_json(403,{'error':'Solicitud externa no permitida'});return
  try:
   size=int(self.headers.get('Content-Length','0'))
   if not 0<size<=65536:raise ValueError('Solicitud no válida')
   payload=json.loads(self.rfile.read(size))
   if not isinstance(payload,dict):raise ValueError('Solicitud no válida')
   self.send_json(200,RECOMMENDER.recommend(payload))
  except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
  except Exception as error:self.send_json(502,{'error':str(error)[:180]})
 def do_HEAD(self):self.do_GET()
 def do_GET(self):
  try:self.account_GET()
  except (BrokenPipeError,ConnectionResetError):pass
  except Exception as error:
   (ROOT/'data'/'account-diagnostic.json').write_text(json.dumps({'type':type(error).__name__,'sqlstate':getattr(error,'sqlstate',None)}),encoding='utf8')
   self.send_json(503,{'error':'El servidor no pudo acceder a tu cuenta. Inténtalo de nuevo.'})
 def account_GET(self):
  route=urlsplit(self.path);path=route.path
  if path=='/healthz':self.send_json(200,{'status':'ok'});return
  if path=='/login.html':
   self.send_response(302);self.send_header('Location','/');self.end_headers();return
  if auth.handle(self):return
  if path.startswith('/api/') and not auth.user(self):self.send_json(401,{'error':'Inicia sesión para continuar.'});return
  if self.headers.get('Sec-Fetch-Site')=='cross-site':self.send_json(403,{'error':'Solicitud externa no permitida'});return
  try:
   if path=='/api/import/config':self.send_json(200,service_import.config());return
   if path=='/api/artist-portrait':
    name=parse_qs(route.query).get('name',[''])[0].strip()
    if not 1<=len(name)<=150:raise ValueError('Artista no válido')
    try:target=APPLE_CATALOGUE.artist(name).get('portrait') or '/icon.png'
    except Exception:target='/icon.png'
    self.send_response(302);self.send_header('Location',target);self.send_header('Cache-Control','private,max-age=300');self.end_headers();return
   if path.startswith('/api/home-portrait/'):
    identity=path.rsplit('/',1)[1]
    artist=next((a for a in HOME_FEED.charts()['artists'] if a.get('id')==identity),None)
    if not artist:self.send_json(404,{'error':'Artista no encontrado'});return
    try:target=APPLE_CATALOGUE.artist(artist['name']).get('hero','/icon.png')
    except Exception:target='/icon.png'
    self.send_response(302);self.send_header('Location',target);self.send_header('Cache-Control','private,max-age=3600');self.end_headers();return
   if path=='/api/home-charts':self.send_json(200,HOME_FEED.charts());return
   if path=='/api/artist-by-name':
    name=parse_qs(route.query).get('q',[''])[0].strip()
    if not 1<=len(name)<=150:raise ValueError('Artista no válido')
    profile=APPLE_CATALOGUE.artist(name,force=parse_qs(route.query).get('refresh')==['1'])
    self.send_json(200,{**profile,'id':'AM-ARTIST-'+profile['appleArtistId']});return
   if path.startswith('/api/artist-profile/'):
    identity=path.rsplit('/',1)[1]
    if not re.fullmatch(r'UC[A-Za-z0-9_-]{22}',identity):raise ValueError('Artista no válido')
    known=next((a for entries in ARTIST_CACHE.values() for a in entries if a['id']==identity),None)
    if known:name=known['name']
    else:
     raw=ARTIST_CATALOGUE.request('browse',browseId=identity)
     header=next(walk(raw,'musicImmersiveHeaderRenderer'),None) or next(walk(raw,'musicVisualHeaderRenderer'),{})
     name=text(header.get('title'))
    profile={**APPLE_CATALOGUE.artist(name,force=parse_qs(route.query).get('refresh')==['1']),'id':identity}
    self.send_json(200,profile);return
   if path.startswith('/api/album/'):
    identity=path.rsplit('/',1)[1]
    self.send_json(200,APPLE_CATALOGUE.album(identity,force=parse_qs(route.query).get('refresh')==['1']) if identity.startswith('AM') else ARTIST_CATALOGUE.album(identity));return
   if path=='/api/catalog':self.send_json(200,{'tracks':CATALOG});return
   if path=='/api/artists':
    q=parse_qs(route.query).get('q',[''])[0].strip()
    if not 1<=len(q)<=120:self.send_json(400,{'error':'Búsqueda no válida'});return
    self.send_json(200,{'artists':search_artists(q)});return
   if path=='/api/search':
    q=parse_qs(route.query).get('q',[''])[0].strip()
    if not 1<=len(q)<=120:self.send_json(400,{'error':'Escribe entre 1 y 120 caracteres'});return
    self.send_json(200,{'tracks':search(q)});return
   if path.startswith('/api/apple-audio/'):
    identity=path.rsplit('/',1)[1];vid=APPLE_CATALOGUE.resolve_audio(identity);STREAM_SOURCES.relay(self,vid);return
   if path.startswith('/api/audio-index/'):
    index=int(path.rsplit('/',1)[1]);STREAM_SOURCES.relay(self,catalog_id(index));return
   if path.startswith('/api/audio/'):
    STREAM_SOURCES.relay(self,path.rsplit('/',1)[1]);return
   if path.startswith('/api/artist-art/'):
    artist_id=path.rsplit('/',1)[1]
    if not re.fullmatch(r'UC[A-Za-z0-9_-]{22}',artist_id):raise ValueError('Artista no válido')
    url=ARTIST_PHOTOS.get(artist_id,'')
    if urlsplit(url).scheme!='https' or urlsplit(url).hostname not in ('yt3.googleusercontent.com','lh3.googleusercontent.com'):self.send_json(404,{'error':'Foto no encontrada'});return
    cached=CACHE/(artist_id+'.jpg')
    if not cached.is_file():
     req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
     with urllib.request.urlopen(req,timeout=15) as response:
      content=response.read(1500000)
      if not response.headers.get_content_type().startswith('image/'):raise ValueError('Foto no válida')
     cached.write_bytes(content)
    self.send_file(cached);return
   if path.startswith('/api/art/'):
    vid=path.rsplit('/',1)[1]
    if vid not in ART:
     if re.fullmatch(r'[A-Za-z0-9_-]{11}',vid):ART[vid]='https://i.ytimg.com/vi/'+vid+'/hqdefault.jpg'
     else:self.send_json(404,{'error':'Portada no encontrada'});return
    req=urllib.request.Request(ART[vid],headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=15) as response:content=response.read(1500000);mime=response.headers.get_content_type()
    if not mime.startswith('image/'):raise ValueError('Portada no válida')
    self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','public,max-age=86400');self.end_headers()
    if self.command!='HEAD':self.wfile.write(content)
    return
   relative='index.html' if path=='/' else path.lstrip('/')
   allowed={'hls.light.min.js','hls-LICENSE.txt','library-tools.js','index.html','app.js','lock.js','audio.js','offline.js','sw.js','install.html','device-client.js','icons/apple-touch-icon.png','icons/icon-192.png','icons/icon-512.png','lucide.js','manifest.webmanifest','icon.png'}
   if relative not in allowed and not re.fullmatch(r'covers/[0-5]\.webp',relative):self.send_json(404,{'error':'No encontrado'});return
   self.send_file(ROOT/relative)
  except (BrokenPipeError,ConnectionResetError):pass
  except Exception as error:self.send_json(502,{'error':str(error)[:180]})
 def send_file(self,path,audio=False):
  if not path.is_file():self.send_json(404,{'error':'No encontrado'});return
  size=path.stat().st_size
  try:start,end,partial=byte_range(self.headers.get('Range'),size)
  except ValueError:
   self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.send_header('Content-Length','0');self.end_headers();return
  self.send_response(206 if partial else 200);self.send_header('Content-Type','audio/mp4' if audio else mimetypes.guess_type(path)[0] or 'application/octet-stream');self.send_header('Content-Length',str(end-start+1));self.send_header('Accept-Ranges','bytes');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','private,max-age=86400' if audio else 'no-cache')
  if partial:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
  self.end_headers()
  if self.command=='HEAD':return
  with path.open('rb') as file:
   file.seek(start);remaining=end-start+1
   while remaining:
    chunk=file.read(min(65536,remaining))
    if not chunk:break
    self.wfile.write(chunk);remaining-=len(chunk)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--host',default=os.environ.get('HOST','127.0.0.1'));parser.add_argument('--port',type=int,default=int(os.environ.get('PORT','4200')));args=parser.parse_args()
 print(f'Vitra móvil: http://{args.host}:{args.port}/',flush=True)
 ThreadingHTTPServer((args.host,args.port),Handler).serve_forever()

