"""Personalized continuation using listening signals and related artist metadata."""
import concurrent.futures,re
class Recommender:
 def __init__(self,catalogue):self.catalogue=catalogue
 def genre_family(self,genre):
  value=self.catalogue.key(genre)
  if 'latin' in value or value in ('reggaeton','dembow'):return 'latin'
  if any(tag in value for tag in ('rock','metal')):return 'rock'
  return value
 def recommend(self,payload):
  seed=payload.get('seed',{});name=str(seed.get('a',''))[:150]
  if not name:raise ValueError('Selecciona una canción para descubrir música similar.')
  try:anchor=self.catalogue.artist(name)
  except ValueError:anchor=self.catalogue.artist(re.split(r',| & ',name)[0].strip())
  key=self.catalogue.key;current=key(anchor['name']);genre=self.genre_family(anchor.get('genre',''))
  blocked={key(v) for v in payload.get('hiddenArtists',[])[:100] if isinstance(v,str)}
  tastes={key(t['artist']):max(-30,min(50,float(t.get('weight',0)))) for t in payload.get('taste',[])[:12] if isinstance(t,dict) and isinstance(t.get('artist'),str)}
  related=anchor.get('relatedArtists',[])[:10];related_keys={key(n) for n in related}
  # Familiar artists influence the order of discovery without overriding similarity.
  related.sort(key=lambda n:tastes.get(key(n),0),reverse=True)
  names=[n for n in related if key(n) not in blocked and key(n)!=current][:6]
  for t in payload.get('taste',[])[:3]:
   n=t.get('artist','')
   if n and key(n) not in blocked|{current} and key(n) not in {key(x) for x in names}:names.append(n)
  def load(n):
   try:return self.catalogue.artist(n)
   except Exception:return None
  with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:profiles=[p for p in pool.map(load,names[:8]) if p]
  profiles=[p for p in profiles if key(p['name']) in related_keys or (genre and self.genre_family(p.get('genre',''))==genre)]
  profiles.append(anchor)
  excluded={str(v) for v in payload.get('exclude',[])[:500]};recent={str(v) for v in payload.get('recent',[])[:50]};favorites={str(v) for v in payload.get('favorites',[])[:300]};skips=payload.get('skips',{})
  candidates=[];seen=set()
  for profile in profiles:
   artist=key(profile['name'])
   if artist in blocked:continue
   for rank,track in enumerate(profile.get('topSongs',[])[:16]):
    identity=str(track.get('appleId') or track.get('vid') or '');fingerprint=key(track['t'])+'|'+key(track['a'])
    if not identity or identity in excluded or fingerprint in excluded or fingerprint in seen or (key(track['t'])==key(seed.get('t','')) and artist==current):continue
    seen.add(fingerprint)
    score=20+20/(rank+1)+min(15,tastes.get(artist,0))+(8 if self.genre_family(profile.get('genre',''))==genre else 0)+(6 if artist in related_keys else 0)+(6 if identity in favorites else 0)-(18 if identity in recent else 0)-min(20,float(skips.get(identity,0))*4)-(15 if artist==current else 0)
    candidates.append((score,artist,{**track,'genre':profile.get('genre','')}))
  candidates.sort(key=lambda c:c[0],reverse=True)
  output=[];counts={};last=''
  while candidates and len(output)<20:
   eligible=[i for i,c in enumerate(candidates) if counts.get(c[1],0)<(1 if c[1]==current else 3) and c[1]!=last and (len(output)>=6 or c[1]!=current)]
   if not eligible:eligible=[i for i,c in enumerate(candidates) if counts.get(c[1],0)<(1 if c[1]==current else 3) and c[1]!=last]
   if not eligible:break
   _,artist,track=candidates.pop(eligible[0]);output.append(track);counts[artist]=counts.get(artist,0)+1;last=artist
  self.catalogue.persist()
  return {'tracks':output,'seedArtist':anchor['name'],'genre':anchor.get('genre','')}
