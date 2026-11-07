"""Official, read-only service import. User access tokens are never persisted."""
import os,json,re,urllib.request,urllib.parse,urllib.error

def config():
 return {'spotifyClientId':os.environ.get('SPOTIFY_CLIENT_ID',''),'spotifyRedirectUri':os.environ.get('SPOTIFY_REDIRECT_URI','http://127.0.0.1:4203/'),'appleDeveloperToken':os.environ.get('APPLE_MUSIC_DEVELOPER_TOKEN','')}

def request_json(base,path,headers):
 target=urllib.parse.urljoin(base,path);a=urllib.parse.urlsplit(base);b=urllib.parse.urlsplit(target)
 if b.scheme!='https' or b.netloc!=a.netloc or b.username or b.password:raise ValueError('Paginación del servicio no válida.')
 try:
  with urllib.request.urlopen(urllib.request.Request(target,headers=headers),timeout=25) as response:
   raw=response.read(4000001)
   if len(raw)>4000000:raise ValueError('La playlist es demasiado grande.')
   return json.loads(raw)
 except urllib.error.HTTPError as error:
  if error.code in (401,403):raise ValueError('El servicio no permitió leer esta playlist. Vuelve a conectarlo y revisa sus permisos.') from None
  if error.code==429:raise ValueError('El servicio limitó las solicitudes. Espera un momento antes de volver a intentarlo.') from None
  raise ValueError('No se pudo leer la playlist en el servicio original.') from None

def collect(base,path,headers,key):
 items=[];seen=set()
 while path:
  if path in seen:raise ValueError('El servicio repitió una página de resultados.')
  seen.add(path);body=request_json(base,path,headers);items.extend(body.get(key,[]))
  if len(items)>1000:raise ValueError('Esta importación admite hasta 1.000 elementos. Divide la playlist y vuelve a intentarlo.')
  path=body.get('next')
 return items

def handle(payload):
 service=payload.get('service');action=payload.get('action');identity=payload.get('id','');token=payload.get('token','')
 if service not in ('spotify','apple') or action not in ('list','tracks'):raise ValueError('Importación no válida.')
 if not isinstance(token,str) or not 10<=len(token)<=10000 or '\n' in token or '\r' in token:raise ValueError('Conecta el servicio para importar tus playlists.')
 if not isinstance(identity,str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,150}',identity or 'list'):raise ValueError('Playlist no válida.')
 if service=='spotify':
  if not config()['spotifyClientId']:raise ValueError('La conexión de Spotify todavía no está activada en Vitra.')
  base='https://api.spotify.com';headers={'Authorization':'Bearer '+token,'Accept':'application/json'}
  if action=='list':
   items=collect(base,'/v1/me/playlists?limit=50',headers,'items')
   return {'playlists':[{'id':p['id'],'name':p.get('name','Playlist')} for p in items if p and p.get('id')]}
  meta=request_json(base,'/v1/playlists/'+identity+'?fields=name',headers);items=collect(base,'/v1/playlists/'+identity+'/items?limit=50',headers,'items');tracks=[]
  for entry in items:
   t=entry.get('item') or entry.get('track') or {}
   if t.get('type','track')=='track' and not entry.get('is_local') and t.get('name') and t.get('artists'):tracks.append({'t':t['name'],'a':', '.join(a['name'] for a in t['artists'])})
  return {'title':meta.get('name','Playlist de Spotify'),'tracks':tracks,'warnings':([str(len(items)-len(tracks))+' elementos sin canción disponible se omitieron.'] if len(items)!=len(tracks) else [])}
 developer=config()['appleDeveloperToken']
 if not developer:raise ValueError('La conexión de Apple Music todavía no está activada en Vitra.')
 base='https://api.music.apple.com';headers={'Authorization':'Bearer '+developer,'Music-User-Token':token,'Accept':'application/json'}
 if action=='list':
  items=collect(base,'/v1/me/library/playlists?limit=100',headers,'data')
  return {'playlists':[{'id':p['id'],'name':p.get('attributes',{}).get('name','Playlist')} for p in items if p.get('id')]}
 meta=request_json(base,'/v1/me/library/playlists/'+identity,headers).get('data',[{}])[0];items=collect(base,'/v1/me/library/playlists/'+identity+'/tracks?limit=100',headers,'data');tracks=[]
 for item in items:
  a=item.get('attributes',{})
  if a.get('name') and a.get('artistName'):tracks.append({'t':a['name'],'a':a['artistName']})
 return {'title':meta.get('attributes',{}).get('name','Playlist de Apple Music'),'tracks':tracks,'warnings':([str(len(items)-len(tracks))+' elementos sin canción disponible se omitieron.'] if len(items)!=len(tracks) else [])}
