"""Public Apple Music page metadata. Ranking is Apple's order, never stream counts."""
import concurrent.futures,datetime,json,os,re,threading,time,unicodedata,urllib.request
from audio_matching import choose
from urllib.parse import urlencode,urlsplit
from html.parser import HTMLParser
class PageData(HTMLParser):
 def __init__(self):super().__init__();self.active=False;self.parts=[]
 def handle_starttag(self,tag,attrs):
  if tag=='script' and dict(attrs).get('id')=='serialized-server-data':self.active=True
 def handle_data(self,data):
  if self.active:self.parts.append(data)
 def handle_endtag(self,tag):
  if tag=='script':self.active=False
class AppleCatalogue:
 def __init__(self,root,art,search,search_fresh=None,fallback_search=None):
  self.root=root;self.art=art;self.search=search;self.lock=threading.RLock();self.cache={};self.songs={};self.urls={};self.audio_cache={};self.audio_misses={};self.flights={};self.latest_jobs=set();self.refresh_jobs=set();self.refresh_after={};self.latest_pool=concurrent.futures.ThreadPoolExecutor(max_workers=2);self.search_fresh=search_fresh;self.fallback_search=fallback_search
  try:
   stored=json.loads((root/'cache'/'apple-catalogue.json').read_text(encoding='utf8'));self.cache=stored.get('cache',{});self.songs=stored.get('songs',{});self.urls=stored.get('urls',{});self.audio_cache=stored.get('audioCache',{})
  except (OSError,ValueError):pass
 @staticmethod
 def key(name):return re.sub(r'[^a-z0-9]','', ''.join(c for c in unicodedata.normalize('NFKD',name.lower()) if not unicodedata.combining(c)))
 def persist(self):
  with self.lock:
   for name,value in [('apple-catalogue.json',{'cache':self.cache,'songs':self.songs,'urls':self.urls,'audioCache':self.audio_cache}),('artwork.json',self.art)]:
    path=self.root/'cache'/name;path.parent.mkdir(exist_ok=True);temporary=path.with_name(name+'.'+str(os.getpid())+'.'+str(threading.get_ident())+'.tmp');temporary.write_text(json.dumps(value),encoding='utf8');temporary.replace(path)
 def get(self,url):
  if urlsplit(url).scheme!='https' or urlsplit(url).hostname not in ('music.apple.com','itunes.apple.com'):raise ValueError('Fuente Apple no válida')
  req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept-Language':'en-US,en;q=0.9'})
  with urllib.request.urlopen(req,timeout=25) as response:return response.read(4000000).decode('utf8')
 def page(self,url):
  parser=PageData();parser.feed(self.get(url));body=json.loads(''.join(parser.parts))
  return body['data'][0]['data']
 def cached(self,key,load,ttl=None,force=False):
  with self.lock:flight=self.flights.setdefault(key,threading.RLock())
  with flight:
   with self.lock:hit=self.cache.get(key)
   age=time.time()-hit[0] if hit else float('inf')
   lifespan=60 if key.startswith('artist:') else 86400
   if key.startswith('AM'):
    try:recent=(datetime.date.today()-datetime.date.fromisoformat(hit[1].get('releaseDate',''))).days<=7 if hit else True
    except ValueError:recent=True
    lifespan=60 if recent else 86400
   if ttl is not None:lifespan=ttl
   valid=hit and (not key.startswith('artist:') or 'relatedArtists' in hit[1] and hit[1].get('artworkVersion')==3)
   if valid and age<(15 if force else lifespan):return hit[1]
   try:value=load()
   except Exception:
    if valid and age<86400:return {**hit[1],'stale':True}
    raise
   with self.lock:self.cache[key]=[time.time(),value];self.persist()
   return value
 def picture(self,item,identity,width=720,height=720):
  url=item.get('dictionary',{}).get('url','')
  if not re.fullmatch(r'is\d+-ssl\.mzstatic\.com',urlsplit(url).hostname or ''):return '/icon.png'
  url=url.replace('{w}',str(width)).replace('{h}',str(height)).replace('{c}','bb').replace('{f}','jpg')
  self.art['AM'+str(identity)]=url
  return '/api/art/AM'+str(identity)
 def artist(self,name,force=False):
  cache_key='artist:'+self.key(name)
  with self.lock:
   hit=self.cache.get(cache_key)
   if not force and hit and 'relatedArtists' in hit[1] and hit[1].get('artworkVersion')==3 and 60<=time.time()-hit[0]<7*86400:
    if cache_key not in self.refresh_jobs and time.time()>=self.refresh_after.get(cache_key,0):
     self.refresh_jobs.add(cache_key);self.refresh_after[cache_key]=time.time()+60;self.latest_pool.submit(self._refresh_artist,name,cache_key)
    return {**hit[1],**({'latestChecking':True,'refreshing':True} if cache_key in self.refresh_jobs else {'stale':True})}
  profile=self.cached(cache_key,lambda:self.load_artist(name),force=force)
  if profile.get('latestChecking'):
   with self.lock:
    if cache_key not in self.latest_jobs:self.latest_jobs.add(cache_key);self.latest_pool.submit(self._finish_latest,cache_key,profile)
  return profile
 def _refresh_artist(self,name,cache_key):
  try:
   self.cached(cache_key,lambda:self.load_artist(name),force=True)
   self.artist(name)
  except Exception:pass
  finally:
   with self.lock:self.refresh_jobs.discard(cache_key)
 def _finish_latest(self,cache_key,profile):
  try:
   candidates=[];seen=set()
   for card in ([profile.get('latest')] if profile.get('latest') else [])+profile.get('albums',[])[:2]+profile.get('singles',[])[:2]:
    if card and card.get('id') not in seen:seen.add(card['id']);candidates.append(card)
   def load(card):
    try:return self.album(card['id'])
    except Exception:return None
   with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:releases=[r for r in pool.map(load,candidates[:5]) if r and r.get('releaseDate') and r['releaseDate']<=datetime.date.today().isoformat()]
   result={**profile,'latestChecking':False}
   if releases:result['latest']=max(releases,key=lambda r:r['releaseDate'])
   with self.lock:
    current=self.cache.get(cache_key)
    if current and current[1].get('verifiedAt')==profile.get('verifiedAt'):self.cache[cache_key]=[current[0],result];self.persist()
  finally:
   with self.lock:self.latest_jobs.discard(cache_key)

 def load_artist(self,name):
  def identity():
   results=json.loads(self.get('https://itunes.apple.com/search?'+urlencode({'term':name,'entity':'musicArtist','country':'us','limit':30})))['results']
   match=next((r for r in results if self.key(r.get('artistName',''))==self.key(name)),None)
   if not match:raise ValueError('No se encontró un perfil coincidente en Apple Music.')
   return match
  match=self.cached('identity:'+self.key(name),identity,ttl=86400)
  url=match['artistLinkUrl'].split('?')[0];data=self.page(url);artist_name=match['artistName'];identity=str(match['artistId']);top=[];albums=[];singles=[];latest=None;hero='/icon.png';banner='';banner_mobile='';banner_video='';banner_video_mobile='';related=[]
  for section in data.get('sections',[]):
   kind=section.get('itemKind','')
   if kind=='artistDetailHeader':
    header=section.get('items',[{}])[0];hero=self.picture(header.get('circleArtwork') or header.get('artwork') or {},'P'+identity)
    wide=header.get('wideArtwork') or {};motion=(header.get('wideVideoArtwork') or {}).get('dictionary',{})
    movie=motion.get('motionArtistFullscreen16x9') or motion.get('motionArtistWide16x9') or next(iter(motion.values()),{})
    if not wide.get('dictionary',{}).get('url') and movie.get('previewFrame'):wide={'dictionary':movie['previewFrame']}
    if wide.get('dictionary',{}).get('url'):banner=self.picture(wide,'B'+identity,1440,810)
    square_motion=(header.get('videoArtwork') or {}).get('dictionary',{});square=next(iter(square_motion.values()),{})
    if isinstance(square,dict) and square.get('previewFrame'):banner_mobile=self.picture({'dictionary':square['previewFrame']},'M'+identity,1000,1000)
    if banner=='/icon.png':banner=''
    if banner_mobile=='/icon.png':banner_mobile=''
    mobile_candidate=square.get('video','') if isinstance(square,dict) else ''
    if urlsplit(mobile_candidate).scheme=='https' and urlsplit(mobile_candidate).hostname=='mvod.itunes.apple.com':banner_video_mobile=mobile_candidate
    candidate=movie.get('video','')
    if urlsplit(candidate).scheme=='https' and urlsplit(candidate).hostname=='mvod.itunes.apple.com':banner_video=candidate
   if kind=='artistFeaturedContentAndTracks':
    item=section.get('items',[{}])[0];featured=item.get('featuredContent',{})
    if featured and 'LatestRelease' in item.get('id',''):
     latest=self.release(featured,artist_name,featured.get('detailText',{}))
    top=[self.track(t,artist_name) for t in item.get('tracks',[])]
   if '.SimilarArtists-' in section.get('id',''):
    related=[r.get('title','') for r in section.get('items',[]) if r.get('contentDescriptor',{}).get('kind')=='artist' and r.get('title')]
   if kind=='squareLockup':
    if '.Albums-' in section.get('id',''):albums=[self.release(t,artist_name) for t in section.get('items',[])]
    elif '.ArtistSingles-' in section.get('id',''):singles=[self.release(t,artist_name) for t in section.get('items',[])]
  if not top and not latest:raise ValueError('Apple Music no devolvió canciones o lanzamientos verificables.')
  return {'artworkVersion':3,'portrait':hero,'banner':banner,'bannerMobile':banner_mobile,'bannerVideo':banner_video,'bannerVideoMobile':banner_video_mobile,'latestChecking':True,'genre':match.get('primaryGenreName',''),'relatedArtists':related,'name':artist_name,'appleArtistId':identity,'hero':hero,'topSongs':top,'albums':albums,'singles':singles,'latest':latest,'ranking':'apple-music-top-songs','source':'Apple Music','sourceUrl':url,'verifiedAt':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 def release(self,item,artist,details=None):
  descriptor=item.get('contentDescriptor',{});identity=str(descriptor.get('identifiers',{}).get('storeAdamID') or item.get('id',''));url=descriptor.get('url','');self.urls[identity]=url
  details=details or {};title=details.get('title') or item.get('title') or ' '.join(x.get('title','') for x in item.get('titleLinks',[]));subtitle=' '.join(x.get('title','') for x in item.get('subtitleLinks',[]));date=details.get('headline','');year=re.search(r'\b(?:19|20)\d{2}\b',date or subtitle)
  return {'id':'AM'+identity,'title':title,'artist':artist,'year':year[0] if year else '', 'dateLabel':date,'kind':'Sencillo' if 'single' in title.lower() else 'EP' if title.lower().endswith(' - ep') else 'Álbum','art':self.picture(item.get('artwork',{}),identity),'trackCountLabel':details.get('subtitle',''),'sourceUrl':url}
 def track(self,item,artist,art=None,album=''):
  descriptor=item.get('contentDescriptor',{});identity=str(descriptor.get('identifiers',{}).get('storeAdamID') or item.get('id',''));seconds=round((item.get('duration') or 0)/1000)
  record={'appleId':identity,'t':item.get('title',''),'a':item.get('artistName') or artist,'album':album or ' '.join(t.get('title','') for t in item.get('subtitleLinks') or []),'d':f'{seconds//60}:{seconds%60:02}','durationSeconds':seconds,'art':self.picture(item.get('artwork') or {},identity) if item.get('artwork') else art or '/icon.png','plays':None,'playsLabel':'','c':'#606066','sourceUrl':descriptor.get('url','')}
  self.songs[identity]=record
  return record
 def album(self,identity,force=False):
  if not re.fullmatch(r'AM\d+',identity):raise ValueError('Álbum Apple no válido')
  return self.cached(identity,lambda:self.load_album(identity[2:]),force=force)
 def load_album(self,identity):
  url=self.urls.get(identity) or 'https://music.apple.com/us/album/'+identity;data=self.page(url);header=next((s['items'][0] for s in data['sections'] if s.get('itemKind')=='containerDetailHeaderLockup'),{})
  artist=', '.join(t.get('title','') for t in header.get('subtitleLinks') or []);title=header.get('title','');art=self.picture(header.get('artwork',{}),identity);year=re.search(r'\b(?:19|20)\d{2}\b',header.get('quaternaryTitle',''));tracks=[]
  for section in data['sections']:
   if section.get('itemKind')=='trackLockup':tracks.extend(self.track(t,artist,art,title) for t in section.get('items',[]) if t.get('contentDescriptor',{}).get('kind')=='song')
  if not tracks:raise ValueError('Apple Music no devolvió las canciones del álbum.')
  footer=next((s['items'][0] for s in data['sections'] if s.get('itemKind')=='containerDetailTracklistFooterLockup'),{})
  date_label=footer.get('description','').split('\n')[0];release_date=''
  for pattern in ('%B %d, %Y','%b %d, %Y'):
   try:release_date=datetime.datetime.strptime(date_label,pattern).date().isoformat();break
   except ValueError:pass
  return {'id':'AM'+identity,'title':title,'artist':artist,'art':art,'year':year[0] if year else '', 'kind':'Sencillo' if 'single' in title.lower() else 'Álbum','tracks':tracks,'sourceUrl':url,'releaseDate':release_date,'dateLabel':date_label,'trackCountLabel':str(len(tracks))+' canciones'}
 def resolve_audio(self,identity,force=False,excluded=()):
  with self.lock:flight=self.flights.setdefault('audio:'+identity,threading.RLock())
  with flight:return self._resolve_audio(identity,force,excluded)
 def _resolve_audio(self,identity,force=False,excluded=()):
  if not identity.isdigit() or identity not in self.songs:raise ValueError('Canción no registrada')
  now=time.time();cached=self.audio_cache.get(identity)
  if not force and cached and now-cached.get('at',0)<86400 and cached.get('vid') not in excluded:return cached['vid']
  if not force and now-self.audio_misses.get(identity,0)<20:raise ValueError('Todavía no encontramos el audio exacto. Vuelve a intentarlo en unos segundos.')
  song=self.songs[identity];query=song['a']+' '+song['t'];search_error=None
  try:choices=self.search(query)
  except Exception as error:choices=[];search_error=error
  match=choose(song,choices,excluded)
  if (not match or force) and self.search_fresh:
   try:match=choose(song,self.search_fresh(query),excluded)
   except Exception as error:search_error=error
  if not match and self.fallback_search:
   try:match=choose(song,self.fallback_search(query+' official audio'),excluded)
   except Exception as error:search_error=error
  if not match and search_error:raise ValueError('No se pudieron consultar todas las fuentes de audio. Revisa la conexión y vuelve a intentarlo.') from None
  if not match:
   self.audio_misses[identity]=now
   raise ValueError('El lanzamiento está en el catálogo, pero todavía no encontramos su audio exacto en YouTube. Se volverá a comprobar al reintentar.')
  self.audio_cache[identity]={'vid':match['vid'],'at':now};self.audio_misses.pop(identity,None);self.persist();return match['vid']
