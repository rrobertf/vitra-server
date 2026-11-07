"""Conservative audio matching: preserve remix/live versions and reject mismatches."""
import re,unicodedata

def key(value):return re.sub(r'[^a-z0-9]','', ''.join(c for c in unicodedata.normalize('NFKD',str(value).lower()) if not unicodedata.combining(c)))
def seconds(track):
 try:return float(track.get('durationSeconds') or sum(int(p)*60**i for i,p in enumerate(reversed(track.get('d','0:00').split(':')))))
 except (ValueError,TypeError):return 0

def choose(song,choices,excluded=()):
 def title(value):
  value=re.sub(r'\s*[\[(]?(?:feat\.?|ft\.?|featuring)\s+.*','',value,flags=re.I)
  value=re.sub(r'\s*[\[(](?:official\s+(?:audio|video|music\s+video|visualizer)|audio\s+oficial|video\s+oficial|lyrics?|lyric\s+video|visualizer|audio)[\])]?\s*',' ',value,flags=re.I)
  return key(value)
 wanted=title(song['t']);artists=[key(a) for a in re.split(r',|&|;',song['a']) if len(a.strip())>2];duration=seconds(song);ranked=[]
 for track in choices:
  if not re.fullmatch(r'[A-Za-z0-9_-]{11}',str(track.get('vid',''))) or track['vid'] in excluded:continue
  raw=track.get('t','');candidate=title(raw);channel=key(track.get('a',''))
  # A video's artist prefix is accepted only when its uploader also matches.
  if candidate!=wanted:
   if not any(a and a in channel and candidate==a+wanted for a in artists):continue
  versions=lambda value:{token for token in ('cover','karaoke','sped up','slowed','instrumental','remix','live','acoustic') if re.search(r'\b'+re.escape(token)+r'\b',value,re.I)}
  if versions(raw)!=versions(song['t']):continue
  matched=[a for a in artists if a in channel]
  if artists and not matched:continue
  length=seconds(track)
  if duration and length and abs(duration-length)>max(15,duration*.1):continue
  score=len(matched)*100+(10 if track.get('verified') else 0)+(5 if track.get('isTopic') else 0)-(abs(duration-length) if duration and length else 8)
  ranked.append((score,track))
 return max(ranked,key=lambda x:x[0])[1] if ranked else None
