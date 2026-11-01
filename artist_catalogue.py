"""Artist and album catalogue parsing; counts always come from the provider."""
import concurrent.futures,datetime,json,re,threading,time,urllib.request
class ArtistCatalogue:
 def __init__(self,root,art,walk,text):
  self.root=root;self.art=art;self.walk=walk;self.text=text;self.cache={};self.lock=threading.Lock()
 def request(self,method,**values):
  body={'context':{'client':{'clientName':'WEB_REMIX','clientVersion':'1.'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d')+'.01.00','hl':'en','gl':'US'}},**values}
  req=urllib.request.Request('https://music.youtube.com/youtubei/v1/'+method+'?prettyPrint=false',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','User-Agent':'Mozilla/5.0','Origin':'https://music.youtube.com'})
  with urllib.request.urlopen(req,timeout=25) as response:return json.load(response)
 def cached(self,key,load):
  with self.lock:
   hit=self.cache.get(key)
  if hit and time.time()-hit[0]<3600:return hit[1]
  value=load()
  with self.lock:self.cache[key]=(time.time(),value)
  return value
 def image(self,item,key):
  from urllib.parse import urlsplit
  for thumbs in self.walk(item,'thumbnails'):
   if not thumbs:continue
   url=thumbs[-1].get('url','')
   if urlsplit(url).hostname in ('yt3.googleusercontent.com','lh3.googleusercontent.com'):
    self.art[key]=re.sub(r'=w\d+-h\d+.*','=w720-h720-l90-rj',url)
    return '/api/art/'+key
  return '/icon.png'
 def persist(self):
  with self.lock:(self.root/'cache'/'artwork.json').write_text(json.dumps(self.art),encoding='utf8')
 @staticmethod
 def plays(value):
  m=re.search(r'([\d,.]+)\s*([KMB]?)\s*(?:plays|views)',value,re.I)
  return round(float(m[1].replace(',',''))*{'':1,'K':1000,'M':1000000,'B':1000000000}[m[2].upper()]) if m else None
 def tracks(self,data,fallback=''):
  result=[];seen=set()
  for r in self.walk(data,'musicResponsiveListItemRenderer'):
   vid=r.get('playlistItemData',{}).get('videoId')
   if not vid:
    endpoints=list(self.walk(r.get('overlay',{}),'watchEndpoint'))
    vid=next((v.get('videoId') for v in endpoints if v.get('videoId')),None)
   if not vid:vid=next((v.get('videoId') for v in self.walk(r.get('flexColumns',[{}])[0],'watchEndpoint') if v.get('videoId')),None)
   if not vid or vid in seen:continue
   columns=r.get('flexColumns',[]);labels=[self.text(c.get('musicResponsiveListItemFlexColumnRenderer',{}).get('text')) for c in columns]
   if not labels:continue
   refs=[];album=''
   for c in columns[1:]:
    for run in c.get('musicResponsiveListItemFlexColumnRenderer',{}).get('text',{}).get('runs',[]):
     ep=run.get('navigationEndpoint',{}).get('browseEndpoint',{});kind=ep.get('browseEndpointContextSupportedConfigs',{}).get('browseEndpointContextMusicConfig',{}).get('pageType')
     if kind=='MUSIC_PAGE_TYPE_ARTIST':refs.append({'id':ep['browseId'],'name':run.get('text','')})
     if kind=='MUSIC_PAGE_TYPE_ALBUM':album=run.get('text','')
   count_label=next((v for v in labels if self.plays(v) is not None),'')
   duration=next((v for v in [self.text(t) for t in self.walk(r.get('fixedColumns',[]),'text')]+labels if re.fullmatch(r'\d+(?::\d{2}){1,2}',v)),'0:00')
   result.append({'vid':vid,'t':labels[0],'a':', '.join(v['name'] for v in refs) or fallback,'artists':refs,'album':album,'d':duration,'art':self.image(r.get('thumbnail',{}),vid),'plays':self.plays(count_label),'playsLabel':count_label,'c':'#606066'})
   seen.add(vid)
  return result
 def release_card(self,r,kind):
  ep=r.get('navigationEndpoint',{}).get('browseEndpoint',{});identity=ep.get('browseId','')
  if not identity.startswith('MPRE'):return None
  label=self.text(r.get('subtitle'));year=re.search(r'\b(?:19|20)\d{2}\b',label)
  return {'id':identity,'title':self.text(r.get('title')),'year':year[0] if year else '', 'kind':kind,'art':self.image(r.get('thumbnailRenderer',{}),identity)}
 def album(self,identity):
  if not re.fullmatch(r'MPRE[A-Za-z0-9_-]{1,100}',identity):raise ValueError('Álbum no válido')
  return self.cached(identity,lambda:self.parse_album(self.request('browse',browseId=identity),identity))
 def parse_album(self,data,identity):
  header=next(self.walk(data,'musicResponsiveHeaderRenderer'),None) or next(self.walk(data,'musicDetailHeaderRenderer'),{})
  artist=self.text(header.get('straplineTextOne'));tracks=self.tracks(data,artist)
  art=self.image(header.get('thumbnail',{}),identity)
  for track in tracks:
   if track['art']=='/icon.png':track['art']=art
  subtitle=self.text(header.get('subtitle'));year=re.search(r'\b(?:19|20)\d{2}\b',subtitle)
  date=''
  # Publication metadata is used to compare the most recent catalogue candidates.
  if tracks:
   try:
    player=self.request('player',videoId=tracks[0]['vid']);meta=next(self.walk(player,'microformatDataRenderer'),{})
    date=meta.get('publishDate','')[:10]
   except Exception:pass
  self.persist()
  return {'id':identity,'title':self.text(header.get('title')),'artist':artist,'year':year[0] if year else '', 'date':date,'kind':'Sencillo' if 'single' in subtitle.lower() else 'Álbum','art':art,'tracks':tracks}
 def artist(self,identity):
  if not re.fullmatch(r'UC[A-Za-z0-9_-]{22}',identity):raise ValueError('Artista no válido')
  return self.cached(identity,lambda:self.parse_artist(self.request('browse',browseId=identity),identity))
 def parse_artist(self,data,identity):
  header=next(self.walk(data,'musicImmersiveHeaderRenderer'),None) or next(self.walk(data,'musicVisualHeaderRenderer'),{})
  name=self.text(header.get('title'));top=[];albums=[];singles=[]
  for shelf in self.walk(data,'musicShelfRenderer'):
   if self.text(shelf.get('title')).lower()=='top songs':
    top=self.tracks(shelf,name)
    ep=next(self.walk(shelf.get('title',{}),'browseEndpoint'),{})
    if ep.get('browseId'):
     try:top=self.tracks(self.request('browse',browseId=ep['browseId'],params=ep.get('params','')),name) or top
     except Exception:pass
    break
  # Strictly rank available songs by the provider's reported play counts.
  top=sorted((t for t in top if t['plays'] is not None),key=lambda t:t['plays'],reverse=True)
  for shelf in self.walk(data,'musicCarouselShelfRenderer'):
   title=' '.join(self.text(v) for v in self.walk(shelf.get('header',{}),'title')).lower()
   if title not in ('albums','singles & eps'):continue
   target=albums if title=='albums' else singles;kind='Álbum' if title=='albums' else 'Sencillo'
   items=list(self.walk(shelf.get('contents',[]),'musicTwoRowItemRenderer'))
   ep=next(self.walk(shelf.get('header',{}),'browseEndpoint'),{})
   if ep.get('browseId'):
    try:items=list(self.walk(self.request('browse',browseId=ep['browseId'],params=ep.get('params','')),'musicTwoRowItemRenderer')) or items
    except Exception:pass
   seen=set()
   for r in items:
    card=self.release_card(r,kind)
    if card and card['id'] not in seen:target.append(card);seen.add(card['id'])
  candidates=albums[:1]+singles[:3];details=[]
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
   for result in pool.map(self.safe_album,candidates):
    if result:details.append(result)
  latest=max(details,key=lambda a:(a['date'] or a['year'],a['year']),default=None)
  hero=self.image(header.get('thumbnail',{}),identity)
  self.persist()
  return {'id':identity,'name':name,'hero':hero,'topSongs':top,'albums':albums,'singles':singles,'latest':latest,'ranking':'reported-play-counts'}
 def safe_album(self,card):
  try:return self.album(card['id'])
  except Exception:return None
