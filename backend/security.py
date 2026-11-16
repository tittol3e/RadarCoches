import ipaddress
from urllib.parse import urlsplit, urlunsplit

def canonical_url(value):
    if value is None or value == '':
        return None
    try:
        u = urlsplit(value.strip())
        host = (u.hostname or '').lower()
        if u.scheme not in ('https', 'http') or not host or u.username or u.password:
            raise ValueError('URL HTTP/HTTPS pública requerida, sin credenciales')
        if host in ('localhost', 'localhost.localdomain') or host.endswith(('.local', '.internal')):
            raise ValueError('No se admiten URLs locales')
        try:
            if not ipaddress.ip_address(host).is_global:
                raise ValueError('No se admiten direcciones privadas')
        except ValueError as exc:
            if 'direcciones' in str(exc):
                raise
        if '.' not in host or u.port not in (None, 80, 443):
            raise ValueError('Dominio o puerto no permitido')
        # URL identity retains query: distinct listings can share a path.
        from urllib.parse import parse_qsl, urlencode
        query = urlencode(sorted((k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
                                 if not k.lower().startswith(('utm_', 'fbclid', 'gclid'))))
        return urlunsplit((u.scheme.lower(), host, u.path.rstrip('/') or '/', query, ''))
    except (TypeError, AttributeError) as exc:
        raise ValueError('URL inválida') from exc

