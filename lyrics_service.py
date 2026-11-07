"""Real synchronized lyrics with metadata matching and plain-text fallback."""
import hashlib,json,re,time,threading,unicodedata,urllib.request,urllib.error,datetime,concurrent.futures
from urllib.parse import urlencode,quote

def key(value):return re.sub(r'[^a-z0-9]','', ''.join(c for c in unicodedata.normalize('NFKD',str(value).lower()) if not unicodedata.combining(c)))
def clean_title(value):
 value=re.sub(r'\s*[\[(](?:official[^\])]*|video oficial|audio oficial|lyrics?|visualizer)[\])]','',value,flags=re.I)
 return re.sub(r'\s+(?:feat\.?|ft\.?)\s+.*$','',value,flags=re.I).strip()
def parse_lrc(text):
 offset=re.search(r'\[offset:([+-]?\d+)\]',text,re.I);offset=max(-60000,min(60000,int(offset[1]))) if offset else 0;lines=[]
 stamp=re.compile(r'\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]');word_stamp=re.compile(r'<(\d{1,3}):(\d{1,2})(?:\.(\d{1,3}))?>')
 def seconds(m):return int(m[1])*60+int(m[2])+int((m[3] or '').ljust(3,'0') or '0')/1000+offset/1000
 for row in text.splitlines():
  stamps=list(stamp.finditer(row))
  if not stamps:continue
  value=stamp.sub('',row).strip();words=[];tags=list(word_stamp.finditer(value))
  for i,t in enumerate(tags):
   part=value[t.end():tags[i+1].start() if i+1<len(tags) else len(value)]
   if part.strip() and int(t[2])<60:words.append({'time':max(0,seconds(t)),'text':part,**({'end':max(0,seconds(tags[i+1]))} if i+1<len(tags) and seconds(tags[i+1])>seconds(t) else {})})
  visible=word_stamp.sub('',value)
  for tag in stamps:
   if int(tag[2])<60:lines.append({'time':max(0,seconds(tag)),'text':visible,'words':words if len(stamps)==1 else []})
 lines.sort(key=lambda l:l['time']);result=[]
 for line in lines[:1500]:
  if result and result[-1]['time']==line['time']:
   if line['text'] and line['text']!=result[-1]['text']:result[-1]['text']+='\n'+line['text'];result[-1]['words']=[]
  else:result.append(line)
 return result
class LyricsService:
 def __init__(self,root):self.directory=root/'cache'/'lyrics';self.directory.mkdir(parents=True,exist_ok=True);self.memory={};self.locks={};self.lock=threading.Lock();self.providers=concurrent.futures.ThreadPoolExecutor(max_workers=4)
 def request(self,url):
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 Vitra/1.0','Accept':'application/json','Referer':'https://music.163.com/'}),timeout=4) as r:
    body=r.read(1000001)
    if len(body)>1000000:raise ValueError('Respuesta de letras demasiado grande.')
    return json.loads(body)
  except urllib.error.HTTPError as error:
   if error.code in (400,404):return None
   raise
 def matches(self,track,row):
  if key(clean_title(track['title']))!=key(clean_title(row.get('trackName',''))):return False
  targets=[key(a) for a in re.split(r',| & | feat\.? | ft\.? ',track['artist'],flags=re.I) if key(a)];artists=key(row.get('artistName',''))
  return bool(artists and any(target in artists for target in targets))
 def convert(self,track,row):
  text=row.get('syncedLyrics') or '';plain=row.get('plainLyrics') or '';lines=parse_lrc(text) if text else [];duration=float(row.get('duration') or 0);actual=track['duration']
  if not actual or not duration or abs(actual-duration)>6:
   if not plain:plain='\n'.join(l['text'] for l in lines)
   lines=[]
  return {'lines':lines,'plain':plain,'instrumental':row.get('instrumental') is True,'source':'LRCLIB','synced':bool(lines)}
 def netease(self,track):
  artist=re.split(r',| & | feat\.? | ft\.? ',track['artist'],flags=re.I)[0]
  data=self.request('https://music.163.com/api/search/get?'+urlencode({'s':artist+' '+track['title'],'type':1,'limit':10}))
  rows=(data or {}).get('result',{}).get('songs',[])
  candidates=[]
  for row in rows[:10]:
   adapted={'trackName':row.get('name',''),'artistName':' & '.join(a.get('name','') for a in row.get('artists',[])),'duration':float(row.get('duration') or 0)/1000}
   if self.matches(track,adapted) and isinstance(row.get('id'),int):candidates.append((abs(track['duration']-adapted['duration']),row,adapted))
  for _,row,adapted in sorted(candidates,key=lambda item:item[0])[:2]:
   body=self.request('https://music.163.com/api/song/lyric?'+urlencode({'id':row['id'],'lv':1})) or {};text=body.get('lrc',{}).get('lyric','')
   if not text or '纯音乐' in text:continue
   adapted.update(syncedLyrics=text,plainLyrics='\n'.join(line['text'] for line in parse_lrc(text)))
   doc=self.convert(track,adapted);doc['source']='NetEase'
   if doc['synced'] or doc['plain']:return doc
  return None
 def ovh(self,track):
  artist=re.split(r',| & ',track['artist'])[0]
  data=self.request('https://api.lyrics.ovh/v1/'+quote(artist,safe='')+'/'+quote(track['title'],safe=''))
  if isinstance(data,dict) and isinstance(data.get('lyrics'),str) and data['lyrics'].strip():return {'lines':[],'plain':data['lyrics'].strip(),'instrumental':False,'source':'Lyrics.ovh','synced':False}
 def cache_lifetime(self,track,doc):
  try:recent=(datetime.date.today()-datetime.date.fromisoformat(str(track.get('releaseDate',''))[:10])).days<=30
  except ValueError:recent=True
  if doc.get('synced') or doc.get('instrumental'):return 86400 if recent else 14*86400
  if doc.get('plain'):return 3600 if recent else 21600
  return 60 if recent else 300
 def get(self,payload):
  title=payload.get('title');artist=payload.get('artist');duration=payload.get('duration',0)
  if not isinstance(title,str) or not isinstance(artist,str) or not 1<=len(title)<=250 or not 1<=len(artist)<=250 or not isinstance(duration,(int,float)) or not 0<=duration<=14400:raise ValueError('Canción no válida para consultar letras.')
  track={'title':clean_title(title),'artist':artist,'duration':float(duration),'releaseDate':payload.get('releaseDate','')};identity=hashlib.sha256((key(track['title'])+'|'+key(artist)+'|'+str(round(duration))).encode()).hexdigest();path=self.directory/(identity+'.json')
  with self.lock:guard=self.locks.setdefault(identity,threading.Lock())
  with guard:
   cached=self.memory.get(identity)
   if not cached:
    try:cached=json.loads(path.read_text(encoding='utf8'))
    except (OSError,ValueError):pass
   if cached and not(payload.get('refresh') and time.time()-cached.get('at',0)>=20) and time.time()-cached.get('at',0)<self.cache_lifetime(track,cached['data']):return cached['data']
   found=None;network_error=False;params={'track_name':track['title'],'artist_name':artist}
   if duration:params['duration']=str(round(duration))
   try:
    exact=self.request('https://lrclib.net/api/get?'+urlencode(params))
    if isinstance(exact,dict) and self.matches(track,exact):found=self.convert(track,exact)
   except Exception:network_error=True
   if not found or not found['synced'] and not found['instrumental']:
    try:
     rows=self.request('https://lrclib.net/api/search?'+urlencode({'track_name':track['title'],'artist_name':re.split(r',| & ',artist)[0]})) or []
     candidates=[r for r in rows[:100] if isinstance(r,dict) and self.matches(track,r)]
     candidates.sort(key=lambda r:(not bool(r.get('syncedLyrics')),abs(duration-float(r.get('duration') or 0))))
     for candidate in candidates:
      doc=self.convert(track,candidate)
      if doc['synced'] or not found and (doc['plain'] or doc['instrumental']):found=doc
      if doc['synced']:break
    except Exception:network_error=True
   if not found or not found.get('synced') and not found.get('instrumental'):
    try:
     # Providers may index a collaboration under a different lead artist.
     query=re.sub(r'[()]',' ',track['title']);query=re.sub(r'\s+',' ',query).strip()
     rows=self.request('https://lrclib.net/api/search?'+urlencode({'q':query})) or []
     candidates=[r for r in rows[:100] if isinstance(r,dict) and self.matches(track,r)]
     candidates.sort(key=lambda r:(not bool(r.get('syncedLyrics')),abs(duration-float(r.get('duration') or 0))))
     for candidate in candidates:
      doc=self.convert(track,candidate)
      if doc['synced'] or not found and (doc['plain'] or doc['instrumental']):found=doc
      if doc['synced']:break
    except Exception:network_error=True
   if not found or not found.get('synced') and not found.get('instrumental'):
    futures=[self.providers.submit(self.netease,track)]
    if not found or not found.get('plain'):futures.append(self.providers.submit(self.ovh,track))
    try:
     for future in concurrent.futures.as_completed(futures,timeout=13):
      try:doc=future.result()
      except Exception:network_error=True;continue
      if doc and (doc.get('synced') or not found or not found.get('plain')):found=doc
      if found and found.get('synced'):break
    except concurrent.futures.TimeoutError:network_error=True
   if not found or not(found.get('lines') or found.get('plain') or found.get('instrumental')):found={'lines':[],'plain':'','instrumental':False,'source':'','synced':False,'unavailable':True,'retryable':network_error}
   found['refreshAfter']=self.cache_lifetime(track,found)
   saved={'at':time.time(),'data':found};self.memory[identity]=saved
   if len(self.memory)>100:self.memory.pop(next(iter(self.memory)))
   if not(found.get('retryable')):path.write_text(json.dumps(saved),encoding='utf8')
   return found
