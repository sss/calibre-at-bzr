from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import socket, time

_server = None

def _get_external_ip():
    'Get IP address of interface used to connect to the outside world'
    try:
        ipaddr = socket.gethostbyname(socket.gethostname())
    except:
        ipaddr = '127.0.0.1'
    if ipaddr == '127.0.0.1':
        for addr in ('192.0.2.0', '198.51.100.0', 'google.com'):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect((addr, 0))
                ipaddr = s.getsockname()[0]
                if ipaddr != '127.0.0.1':
                    return ipaddr
            except:
                time.sleep(0.3)
    return ipaddr

_ext_ip = None
def get_external_ip():
    global _ext_ip
    if _ext_ip is None:
        _ext_ip = _get_external_ip()
    return _ext_ip

def start_server():
    global _server
    if _server is None:
        from calibre.utils.Zeroconf import Zeroconf
        _server = Zeroconf(bindaddress=get_external_ip())
    return _server

def publish(desc, type, port, properties=None, add_hostname=True):
    '''
    Publish a service.

    :param desc: Description of service
    :param type: Name and type of service. For example _stanza._tcp
    :param port: Port the service listens on
    :param properties: An optional dictionary whose keys and values will be put
                       into the TXT record.
    '''
    port = int(port)
    server = start_server()
    if add_hostname:
        try:
            hostname = socket.gethostname().partition('.')[0]
        except:
            hostname = 'Unknown'
        desc += ' (on %s)'%hostname
    local_ip = get_external_ip()
    type = type+'.local.'
    from calibre.utils.Zeroconf import ServiceInfo
    service = ServiceInfo(type, desc+'.'+type,
                          address=socket.inet_aton(local_ip),
                          port=port,
                          properties=properties,
                          server=hostname+'.local.')
    server.registerService(service)

def stop_server():
    global _server
    if _server is not None:
        _server.close()
