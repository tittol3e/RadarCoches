"""No provider scrapes or fetches unapproved URLs."""
from typing import Protocol

class Provider(Protocol):
    def search(self, filters: dict): ...
    def fetch_if_authorized(self, url: str): ...
    def status(self): ...
    def usage(self): ...

class UnavailableProvider:
    def __init__(self,name):
        self.name = name
    def status(self):
        return {'name':self.name,'available':False,'message':'Sin API autorizada configurada. Importación manual de fichas, CSV o JSON disponible.'}
    def search(self,filters):
        return {'items':[],'status':self.status()}
    def fetch_if_authorized(self,url):
        raise ValueError('Acceso remoto no autorizado/configurado; aporte datos manualmente')
    def usage(self):
        return {'requests':0,'cost':0}

PROVIDERS = [UnavailableProvider(n) for n in ('Wallapop','Milanuncios','Coches.net','AutoScout24')]

