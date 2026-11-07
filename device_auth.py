"""Device-local library mode: no accounts or personal state on the server."""
def user(handler):
 return {'id':'device-local','name':'Este dispositivo','email':''}
def handle(handler):
 from urllib.parse import urlsplit
 path=urlsplit(handler.path).path
 if path.startswith('/api/account/') or path=='/api/user-data':
  handler.send_json(404,{'error':'La biblioteca se guarda en este dispositivo.'})
  return True
 return False
