"""Public Apple Music page metadata. Ranking is Apple's order, never stream counts."""
import concurrent.futures,datetime,json,re,threading,time,unicodedata,urllib.request
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
 def __init__(self,root,art,search):
  self.root=root;self.art=art;self.search=search;self.lock=threading.RLock();self.cache={};self.songs={};self.urls={}
  try:
   stored=json.loads((root/'cache'/'apple-catalogue.json').read_text(encoding='utf8'));self.cache=stored.get('cache',{});self.songs=stored.get('songs',{});self.urls=stored.get('urls',{})
  except (OSError,ValueError):pass
 @staticmethod
 def key(name):return re.sub(r'[^a-z0-9]','', ''.join(c for c in unicodedata.normalize('NFKD',name.lower()) if not unicodedata.combining(c)))
 def persist(self):
  with self.lock:
   (self.root/'cache'/'apple-catalogue.json').write_text(json.dumps({'cache':self.cache,'songs':self.songs,'urls':self.urls}),encoding='utf8')
   (self.root/'cache'/'artwork.json').write_text(json.dumps(self.art),encoding='utf8')
 def get(self,url):
  if urlsplit(url).scheme!='https' or urlsplit(url).hostname not in ('music.apple.com','itunes.apple.com'):raise ValueError('Fuente Apple no válida')
  req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept-Language':'en-US,en;q=0.9'})
  with urllib.request.urlopen(req,timeout=25) as response:return response.read(4000000).decode('utf8')
 def page(self,url):
  parser=PageData();parser.feed(self.get(url));body=json.loads(''.join(parser.parts))
  return body['data'][0]['data']
 def cached(self,key,load):
  with self.lock:hit=self.cache.get(key)
  if hit and time.time()-hit[0]<900 and not(key.startswith('artist:') and (not hit[1].get('latest') or 'relatedArtists' not in hit[1])) and not(key.startswith('AM') and not hit[1].get('releaseDate')):return hit[1]
  value=load()
  with self.lock:self.cache[key]=[time.time(),value];self.persist()
  return value
 def picture(self,item,identity):
  url=item.get('dictionary',{}).get('url','')
  if not re.fullmatch(r'is\d+-ssl\.mzstatic\.com',urlsplit(url).hostname or ''):return '/icon.png'
  url=url.replace('{w}','720').replace('{h}','720').replace('{c}','bb').replace('{f}','jpg')
  self.art['AM'+str(identity)]=url
  return '/api/art/AM'+str(identity)
 def artist(self,name):
  return self.cached('artist:'+self.key(name),lambda:self.load_artist(name))
 def load_artist(self,name):
  results=json.loads(self.get('https://itunes.apple.com/search?'+urlencode({'term':name,'entity':'musicArtist','country':'us','limit':30})))['results']
  match=next((r for r in results if self.key(r.get('artistName',''))==self.key(name)),None)
  if not match:raise ValueError('No se encontró un perfil coincidente en Apple Music.')
  url=match['artistLinkUrl'].split('?')[0];data=self.page(url);artist_name=match['artistName'];identity=str(match['artistId']);top=[];albums=[];singles=[];latest=None;hero='/icon.png';related=[]
  for section in data.get('sections',[]):
   kind=section.get('itemKind','')
   if kind=='artistDetailHeader':
    header=section.get('items',[{}])[0];hero=self.picture(header.get('circleArtwork',{}),identity)
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
  if not latest and (albums or singles):
   cards=albums+singles;newest_year=max(c['year'] for c in cards);candidates=[c for c in cards if c['year']==newest_year]
   def load(card):
    try:return self.album(card['id'])
    except Exception:return None
   with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:releases=[r for r in pool.map(load,candidates) if r and r.get('releaseDate')]
   latest=max(releases,key=lambda r:r['releaseDate'],default=None)
  if not top and not latest:raise ValueError('Apple Music no devolvió canciones o lanzamientos verificables.')
  return {'genre':match.get('primaryGenreName',''),'relatedArtists':related,'name':artist_name,'appleArtistId':identity,'hero':hero,'topSongs':top,'albums':albums,'singles':singles,'latest':latest,'ranking':'apple-music-top-songs','source':'Apple Music','sourceUrl':url,'verifiedAt':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 def release(self,item,artist,details=None):
  descriptor=item.get('contentDescriptor',{});identity=str(descriptor.get('identifiers',{}).get('storeAdamID') or item.get('id',''));url=descriptor.get('url','');self.urls[identity]=url
  details=details or {};title=details.get('title') or item.get('title') or ' '.join(x.get('title','') for x in item.get('titleLinks',[]));subtitle=' '.join(x.get('title','') for x in item.get('subtitleLinks',[]));date=details.get('headline','');year=re.search(r'\b(?:19|20)\d{2}\b',date or subtitle)
  return {'id':'AM'+identity,'title':title,'artist':artist,'year':year[0] if year else '', 'dateLabel':date,'kind':'Sencillo' if 'single' in title.lower() else 'EP' if title.lower().endswith(' - ep') else 'Álbum','art':self.picture(item.get('artwork',{}),identity),'trackCountLabel':details.get('subtitle',''),'sourceUrl':url}
 def track(self,item,artist,art=None,album=''):
  descriptor=item.get('contentDescriptor',{});identity=str(descriptor.get('identifiers',{}).get('storeAdamID') or item.get('id',''));seconds=round((item.get('duration') or 0)/1000)
  record={'appleId':identity,'t':item.get('title',''),'a':item.get('artistName') or artist,'album':album or ' '.join(t.get('title','') for t in item.get('subtitleLinks') or []),'d':f'{seconds//60}:{seconds%60:02}','durationSeconds':seconds,'art':self.picture(item.get('artwork') or {},identity) if item.get('artwork') else art or '/icon.png','plays':None,'playsLabel':'','c':'#606066','sourceUrl':descriptor.get('url','')}
  self.songs[identity]=record
  return record
 def album(self,identity):
  if not re.fullmatch(r'AM\d+',identity):raise ValueError('Álbum Apple no válido')
  return self.cached(identity,lambda:self.load_album(identity[2:]))
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
 def resolve_audio(self,identity):
  if not identity.isdigit() or identity not in self.songs:raise ValueError('Canción no registrada')
  key='audio:'+identity
  if key in self.urls:return self.urls[key]
  song=self.songs[identity];choices=self.search(song['a']+' '+song['t'])
  def title_key(value):return self.key(re.sub(r'\s*[\[(]?(?:feat\.?|ft\.?|featuring)\s+.*','',value,flags=re.I))
  title=title_key(song['t'])
  candidates=[t for t in choices if title_key(t['t'])==title]
  if not candidates:raise ValueError('No se encontró la versión exacta de esta canción en YouTube.')
  target_artists=[self.key(v) for v in re.split(r',|&',song['a']) if len(v.strip())>2]
  def score(t):
   artist_match=sum(a in self.key(t['a']) for a in target_artists)
   parts=t.get('d','0:00').split(':');duration=sum(int(part)*60**i for i,part in enumerate(reversed(parts)) if part.isdigit());target=song.get('durationSeconds',0)
   return artist_match*1000-(min(500,abs(duration-target)) if duration and target else 0)
  candidates.sort(key=score,reverse=True)
  if target_artists and score(candidates[0])<=0:raise ValueError('No se encontró una coincidencia del artista en YouTube.')
  self.urls[key]=candidates[0]['vid'];self.persist();return self.urls[key]
