"""Match portable playlist metadata against the public Apple catalogue."""
import json,re,urllib.parse

def resolve(payload,catalogue):
 title=payload.get('title');artist=payload.get('artist')
 if not isinstance(title,str) or not isinstance(artist,str) or not 1<=len(title)<=250 or not 1<=len(artist)<=250:raise ValueError('Canción o artista no válidos.')
 query=urllib.parse.urlencode({'term':artist+' '+title,'entity':'song','limit':15,'country':'us'})
 rows=json.loads(catalogue.get('https://itunes.apple.com/search?'+query)).get('results',[])
 def key(s):return catalogue.key(s)
 wanted=key(title);artist_key=key(artist)
 matches=[r for r in rows if key(r.get('trackName',''))==wanted and (key(r.get('artistName',''))==artist_key or key(r.get('artistName','')) in [key(a) for a in re.split(r',| & |;',artist)])]
 if not matches:return {'match':None}
 row=matches[0];identity=str(row['trackId']);seconds=round(row.get('trackTimeMillis',0)/1000);picture=row.get('artworkUrl100','');art='/icon.png'
 if picture.startswith('https://') and re.fullmatch(r'is\d+-ssl\.mzstatic\.com',urllib.parse.urlsplit(picture).hostname or ''):
  catalogue.art['AM'+identity]=re.sub(r'/\d+x\d+bb', '/720x720bb',picture);art='/api/art/AM'+identity
 record={'appleId':identity,'t':row['trackName'],'a':row['artistName'],'album':row.get('collectionName',''),'d':f'{seconds//60}:{seconds%60:02}','durationSeconds':seconds,'art':art,'c':'#606066','sourceUrl':row.get('trackViewUrl','')}
 with catalogue.lock:catalogue.songs[identity]=record;catalogue.persist()
 return {'match':record}
