"""Real regional Apple Music charts and Vitra's independent listening mixes."""
import concurrent.futures,datetime,json,re,threading,time,urllib.request
from collections import Counter
from urllib.parse import urlsplit,unquote
class HomeFeed:
 VERSION=3
 MARKETS=[('sanjuan','San Juan, Puerto Rico'),('mx','México'),('co','Colombia'),('do','República Dominicana'),('us','Estados Unidos')]
 SAN_JUAN='https://music.apple.com/us/playlist/top-25-san-juan/pl.2227df646d5d4c53808310928a8d503a'
 def __init__(self,catalogue,recommender,root):
  self.catalogue=catalogue;self.recommender=recommender;self.root=root;self.lock=threading.Lock();self.popular=None;self.personal={};self.regions={};self.refreshing=False;self.retry_after=0
  try:self.popular=json.loads((root/'cache'/'home-charts.json').read_text(encoding='utf8'))
  except (OSError,ValueError):pass
  try:self.regions=json.loads((root/'cache'/'home-regions.json').read_text(encoding='utf8'))
  except (OSError,ValueError):pass
 def _region(self,market,label):
  now=time.time();cached=self.regions.get(market)
  if cached and now-cached.get('fetchedAt',0)<3600:return cached
  try:
   tracks=[];portraits={};updated=''
   if market=='sanjuan':
    url=self.SAN_JUAN;data=self.catalogue.page(url)
    for section in data.get('sections',[]):
     if section.get('itemKind')=='bubbleLockup':
      for item in section.get('items',[]):
       descriptor=item.get('contentDescriptor',{});identity=str(descriptor.get('identifiers',{}).get('storeAdamID',''))
       if descriptor.get('kind')=='artist' and identity.isdigit():portraits[identity]=self.catalogue.picture(item.get('artwork',{}),identity)
     if section.get('itemKind')!='trackLockup':continue
     for item in section.get('items',[]):
      if item.get('contentDescriptor',{}).get('kind')!='song':continue
      track=self.catalogue.track(item,item.get('artistName',''));links=item.get('subtitleLinks',[]);primary=next((link for link in links if link.get('segue',{}).get('destination',{}).get('contentDescriptor',{}).get('kind')=='artist'),{})
      descriptor=primary.get('segue',{}).get('destination',{}).get('contentDescriptor',{})
      track.update(artistId=str(descriptor.get('identifiers',{}).get('storeAdamID','')),artistName=primary.get('title') or track['a'],chartRank=len(tracks)+1,market=market,genres=[],genre='');tracks.append(track)
   else:
    url='https://rss.marketingtools.apple.com/api/v2/'+market+'/music/most-played/100/songs.json';req=urllib.request.Request(url,headers={'User-Agent':'Vitra/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=12) as response:feed=json.load(response)['feed']
    updated=feed.get('updated','')
    for rank,item in enumerate(feed['results'],1):
     identity=str(item.get('id',''));image=item.get('artworkUrl100','')
     if not identity.isdigit() or not re.fullmatch(r'is\d+-ssl\.mzstatic\.com',urlsplit(image).hostname or ''):continue
     self.catalogue.art['AM'+identity]=re.sub(r'/\d+x\d+bb\.', '/720x720bb.',image)
     genres=[g['name'] for g in item.get('genres',[]) if g.get('genreId')!='34'];artist=item['artistName']
     primary=unquote(urlsplit(item.get('artistUrl','')).path.split('/')[-2]).replace('-',' ').title() if (',' in artist or ' & ' in artist) and item.get('artistUrl') else artist
     track={'appleId':identity,'t':item['name'],'a':artist,'d':'0:00','art':'/api/art/AM'+identity,'c':'#606066','genre':genres[0] if genres else '', 'genres':genres,'artistId':str(item.get('artistId','')),'artistName':primary,'chartRank':rank,'sourceUrl':item.get('url',''),'market':market}
     previous=self.catalogue.songs.get(identity,{})
     if previous.get('durationSeconds'):track.update(d=previous['d'],durationSeconds=previous['durationSeconds'])
     tracks.append(track)
   if not tracks:raise ValueError('Lista vacía')
   return {'market':market,'label':label,'tracks':tracks,'portraits':portraits,'updatedAt':updated,'fetchedAt':now,'sourceUrl':url}
  except Exception:
   if cached and now-cached.get('fetchedAt',0)<7*86400:return cached
   return None
 @staticmethod
 def _blend(groups,limit=24,per_artist=2):
  output=[];seen=set();artists=Counter();length=max((len(g['tracks']) for g in groups),default=0)
  for rank in range(length):
   for group in groups:
    if rank>=len(group['tracks']):continue
    track=group['tracks'][rank];identity=track['appleId'];artist=track.get('artistId') or track.get('artistName') or track['a']
    if identity in seen or artists[artist]>=per_artist:continue
    seen.add(identity);artists[artist]+=1;output.append(track)
    if len(output)>=limit:return output
  return output
 def _build(self):
  with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:groups=[g for g in pool.map(lambda pair:self._region(*pair),self.MARKETS) if g]
  if not groups:raise ValueError('No se pudieron actualizar las listas regionales. Inténtalo de nuevo.')
  self.regions={g['market']:g for g in groups};available={g['market']:g for g in groups};mixed=self._blend(groups);regions_label=', '.join(g['label'] for g in groups)
  sections=[{'id':'chart','title':'En tendencia','subtitle':'Selección de listas regionales','tracks':mixed}]
  if 'sanjuan' in available:sections.append({'id':'chart:sanjuan','title':'Lo que suena en Puerto Rico','subtitle':'Top 25: San Juan','tracks':available['sanjuan']['tracks']})
  for market in ('mx','co','do'):
   if market in available:
    group=available[market];sections.append({'id':'chart:'+market,'title':'Lo más escuchado en '+group['label'],'subtitle':'Lista de '+group['label'],'tracks':group['tracks'][:20]})
  pool=self._blend(groups,250,5);counts=Counter(genre for t in pool for genre in t.get('genres',[]))
  for genre,_ in counts.most_common(7):
   selected=[t for t in pool if genre in t.get('genres',[])]
   if len(selected)>=3:sections.append({'id':'genre:'+genre,'title':genre,'subtitle':'Descubre más en las listas regionales','tracks':selected[:12]})
  portraits={k:v for g in groups for k,v in g.get('portraits',{}).items()};artists=[];seen=set()
  for t in self._blend(groups,100,1):
   identity=t.get('artistId','')
   if not identity.isdigit() or identity in seen:continue
   seen.add(identity);artists.append({'id':identity,'name':t.get('artistName') or t['a'],'art':t['art'],'photo':portraits.get(identity,''),'market':t['market']})
   if len(artists)>=16:break
  for g in groups:
   for t in g['tracks']:
    identity=t['appleId'];previous=self.catalogue.songs.get(identity,{})
    if previous.get('durationSeconds') and not t.get('durationSeconds'):t={**t,'d':previous['d'],'durationSeconds':previous['durationSeconds']}
    self.catalogue.songs[identity]=t
  now=time.time();value={'version':self.VERSION,'sections':sections,'artists':artists,'fetchedAt':now,'verifiedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sourceLabel':'Tendencias regionales','regionsLabel':regions_label,'sources':[{k:g[k] for k in ('market','label','sourceUrl','updatedAt','fetchedAt')} for g in groups],'unavailableMarkets':[code for code,_ in self.MARKETS if code not in available],'staleMarkets':[g['market'] for g in groups if now-g['fetchedAt']>=3600]}
  self.catalogue.persist();cache=self.root/'cache';cache.mkdir(exist_ok=True);(cache/'home-regions.json').write_text(json.dumps(self.regions),encoding='utf8');(cache/'home-charts.json').write_text(json.dumps(value),encoding='utf8');return value
 def _refresh(self):
  try:value=self._build()
  except Exception:
   with self.lock:self.refreshing=False;self.retry_after=time.time()+60
   return
  with self.lock:self.popular=value;self.refreshing=False
 def charts(self):
  with self.lock:
   cached=self.popular if self.popular and self.popular.get('version')==self.VERSION else None
   if cached:
    if time.time()-cached.get('fetchedAt',0)>=3600 and not self.refreshing and time.time()>=self.retry_after:
     self.refreshing=True;threading.Thread(target=self._refresh,daemon=True).start()
    return cached
  # Cold load only; following requests use the regional cache immediately.
  with self.lock:
   if self.popular and self.popular.get('version')==self.VERSION:return self.popular
   value=self._build();self.popular=value;return value
 def top_picks(self,payload,bundles):
  key=self.catalogue.key;blocked={key(n) for n in payload.get('hiddenArtists',[]) if isinstance(n,str)};excluded={str(v) for v in payload.get('exclude',[])};recent={str(v) for v in payload.get('recent',[])}
  picks=[];seen=set()
  def allowed(name):return not any(b and b in key(name) for b in blocked)
  def push(item,identity):
   if identity in seen:return
   seen.add(identity);picks.append(item)
  for section,anchor,recommendation in bundles[:4]:
   reason='Porque escuchas '+anchor['name'];tracks=[t for t in recommendation.get('tracks',[]) if allowed(t['a']) and str(t.get('appleId') or t.get('vid') or '') not in excluded and key(t['t'])+'|'+key(t['a']) not in excluded]
   fresh=[t for t in tracks if str(t.get('appleId') or t.get('vid') or '') not in recent];song=next(iter(fresh or tracks),None)
   if song:push({'kind':'song','title':song['t'],'artist':song['a'],'art':song.get('art','/icon.png'),'reason':reason,'track':song},'song:'+str(song.get('appleId') or song.get('vid')))
   target=anchor
   if song:
    name=re.split(r',| & ',song['a'])[0].strip()
    if key(name)!=key(anchor['name']):
     try:target=self.catalogue.artist(name)
     except Exception:pass
   if allowed(target['name']):
    push({'kind':'artist','title':target['name'],'artist':target['name'],'art':target.get('hero','/icon.png'),'reason':reason},'artist:'+key(target['name']))
   for profile in (target,anchor):
    if not allowed(profile['name']):continue
    albums=[a for a in profile.get('albums',[]) if a.get('id') and ('album:'+a['id']) not in seen]
    if not albums:continue
    album=albums[0];push({'kind':'album','title':album['title'],'artist':profile['name'],'art':album.get('art','/icon.png'),'reason':reason,'album':album},'album:'+album['id']);break
  return picks[:12]
 def mixes(self,payload,user_id):
  taste=[t for t in payload.get('taste',[])[:12] if isinstance(t,dict) and isinstance(t.get('artist'),str) and float(t.get('weight',0))>0]
  if not taste:return {'sections':[],'picks':[]}
  taste.sort(key=lambda t:float(t.get('weight',0)),reverse=True)
  signature=json.dumps({k:payload.get(k) for k in ('taste','hiddenArtists','exclude','recent','favorites','skips')},sort_keys=True)
  hit=self.personal.get(user_id)
  if hit and hit[0]==signature and time.time()-hit[1]<600:return hit[2]
  def load(t):
   try:
    profile=self.catalogue.artist(t['artist']);top=profile.get('topSongs',[])
    if not top:return None
    result=self.recommender.recommend({**payload,'seed':top[0]})
    return ({'id':'taste:'+self.catalogue.key(t['artist']),'title':'Porque escuchas '+t['artist'],'subtitle':profile.get('genre',''),'tracks':result['tracks'][:9]},profile,result)
   except Exception:return None
  with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:bundles=[s for s in pool.map(load,taste) if s and s[0]['tracks']]
  sections=[b[0] for b in bundles];mixed=[];seen=set();counts=Counter()
  for row in range(9):
   for section in sections:
    if row>=len(section['tracks']):continue
    track=section['tracks'][row];identity=track.get('appleId') or track.get('vid');artist=track['a']
    if identity in seen or counts[artist]>=2:continue
    seen.add(identity);counts[artist]+=1;mixed.append(track)
  if mixed:sections.insert(0,{'id':'personal','title':'Tu mezcla','subtitle':'Todos tus gustos, en un solo lugar','tracks':mixed[:24]})
  result={'sections':sections,'picks':self.top_picks(payload,bundles)}
  if len(self.personal)>100:self.personal.clear()
  self.personal[user_id]=(signature,time.time(),result);return result

 def new_releases(self,payload):
  taste=sorted([t for t in payload.get('taste',[])[:12] if isinstance(t,dict) and isinstance(t.get('artist'),str) and isinstance(t.get('weight'),(int,float)) and t['weight']>0],key=lambda t:t['weight'],reverse=True)
  blocked={self.catalogue.key(a) for a in payload.get('hiddenArtists',[]) if isinstance(a,str)}
  names=[t['artist'] for t in taste if self.catalogue.key(t['artist']) not in blocked][:8]
  def load(name):
   try:
    profile=self.catalogue.artist(name);latest=profile.get('latest')
    if not latest:return None
    return {k:latest[k] for k in ('id','title','artist','art','kind','year','releaseDate','dateLabel','sourceUrl') if k in latest}
   except Exception:return None
  with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:items=[r for r in pool.map(load,names) if r]
  unique={r['id']:r for r in items};releases=sorted(unique.values(),key=lambda r:r.get('releaseDate') or r.get('year',''),reverse=True)
  return {'releases':releases,'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat()}
