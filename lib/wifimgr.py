import network
import socket
import ure
from machine import Timer
import time
import errno
from lib.microDNSSrv import MicroDNSSrv

NETWORK_PROFILES = 'wifi.dat'

wlan_ap = network.WLAN(network.AP_IF)
wlan_sta = network.WLAN(network.STA_IF)


class CaptiveNetworkTimeoutException(Exception):
    pass

class WifiManager:

    # authmodes: 0=open, 1=WEP, 2=WPA-PSK, 3=WPA2-PSK, 4=WPA/WPA2-PSK
    def __init__(self, ssid='TimeLapseCam', password='', authmode=0):
        self.ssid = ssid
        self.password = password
        self.authmode = authmode
        self.server_socket = None

    def get_connection(self, enter_captive_portal_if_needed=True):
        """return a working WLAN(STA_IF) instance or None"""

        # First check if there already is any connection:
        if wlan_sta.isconnected():
            return wlan_sta

        connected = False
        try:
            # ESP connecting to WiFi takes time, wait a bit and try again:
            time.sleep(3)
            if wlan_sta.isconnected():
                return wlan_sta

            # Read known network profiles from file
            profiles = read_profiles()

            # Search WiFis in range
            wlan_sta.active(True)
            networks = wlan_sta.scan()

            AUTHMODE = {0: "open", 1: "WEP", 2: "WPA-PSK", 3: "WPA2-PSK", 4: "WPA/WPA2-PSK"}
            for ssid, bssid, channel, rssi, authmode, hidden in sorted(networks, key=lambda x: x[3], reverse=True):
                ssid = ssid.decode('utf-8')
                encrypted = authmode > 0
                print("ssid: %s chan: %d rssi: %d authmode: %s" % (ssid, channel, rssi, AUTHMODE.get(authmode, '?')))
                if encrypted:
                    if ssid in profiles:
                        password = profiles[ssid]
                        connected = do_connect(ssid, password)
                    else:
                        print("skipping unknown encrypted network")
                else:  # open
                    connected = do_connect(ssid, None)
                if connected:
                    break

        except OSError as e:
            print("exception", str(e))

        # start web server for connection manager:
        if not connected and enter_captive_portal_if_needed:
            connected = self.start()

        return wlan_sta if connected else None


    def stop(self):
        if self.server_socket:
            self.server_socket.close()
            self.server_socket = None

    
    def start(self, port=80):
        addr = socket.getaddrinfo('0.0.0.0', port)[0][-1]

        self.stop()

        wlan_sta.active(True)
        wlan_ap.active(True)

        wlan_ap.config(essid=self.ssid, password=self.password, authmode=self.authmode)

        self.server_socket = socket.socket()
        self.server_socket.bind(addr)
        self.server_socket.listen(1)

        mdns = MicroDNSSrv.Create({ '*' : '192.168.4.1' })

        print("Running captive portal... for 5 minutes")
        print('Connect to WiFi ssid ' + self.ssid + ', default password: ' + self.password)
        print('and open browser window (captive portal should redirect)')
        print('Listening on:', addr)

        def times_up(t):
            print("Captive portal time is up.")
            mdns.Stop()
            self.stop()
            wlan_ap.active(False)
            raise CaptiveNetworkTimeoutException("Captive portal time is up")
        
        timer_length = 5 * 60 * 1000  # 5 minutes
        timer = Timer(-1, period=timer_length, mode=Timer.ONE_SHOT, callback=times_up)
        while True:
            if wlan_sta.isconnected():
                # Allow confirmation page to display before shutting down network
                timer.deinit()
                time.sleep(3)
                mdns.Stop()
                self.stop()
                wlan_ap.active(False)
                return True

            client, addr = self.server_socket.accept()
            print('client connected from', addr)
            try:
                client.settimeout(5.0)

                request = b""
                try:
                    while "\r\n\r\n" not in request:
                        request += client.recv(512)
                except OSError:
                    pass

                # Handle form data from Safari on macOS and iOS; it sends \r\n\r\nssid=<ssid>&password=<password>
                try:
                    request += client.recv(1024)
                    print("Received form data after \\r\\n\\r\\n(i.e. from Safari on macOS or iOS)")
                except OSError:
                    pass

                print("Request is: {}".format(request))
                if "HTTP" not in request:  # skip invalid requests
                    continue

                # version 1.9 compatibility
                try:
                    url = ure.search("(?:GET|POST) /(.*?)(?:\\?.*?)? HTTP", request).group(1).decode("utf-8").rstrip("/")
                except Exception:
                    url = ure.search("(?:GET|POST) /(.*?)(?:\\?.*?)? HTTP", request).group(1).rstrip("/")
                print("URL is {}".format(url))


                # TODO getting "generate_204 as address"
                if url == "configure":
                    handle_configure(client, request)
                else:
                    handle_root(client)

            finally:
                client.close()

    def get_signal_strength(self):
        if wlan_sta.isconnected():
            return wlan_sta.status('rssi')
        return None



def read_profiles():
    with open(NETWORK_PROFILES) as f:
        lines = f.readlines()
    profiles = {}
    for line in lines:
        ssid, password = line.strip("\n").split(";")
        profiles[ssid] = password
    return profiles



def write_profiles(profiles):
    lines = []
    for ssid, password in profiles.items():
        lines.append("%s;%s\n" % (ssid, password))
    with open(NETWORK_PROFILES, "w") as f:
        f.write(''.join(lines))


def do_connect(ssid, password):
    wlan_sta.active(True)
    if wlan_sta.isconnected():
        return None
    print('Trying to connect to %s...' % ssid)
    wlan_sta.connect(ssid, password)
    for retry in range(200):
        connected = wlan_sta.isconnected()
        if connected:
            break
        time.sleep(0.1)
        print('.', end='')
    if connected:
        print('\nConnected. Network config: ', wlan_sta.ifconfig())
    else:
        print('\nFailed. Not Connected to: ' + ssid)
    return connected


def send_header(client, status_code=200, content_length=None ):
    client.sendall("HTTP/1.0 {} OK\r\n".format(status_code))
    client.sendall("Content-Type: text/html\r\n")
    if content_length is not None:
        client.sendall("Content-Length: {}\r\n".format(content_length))
    client.sendall("\r\n")


def send_response(client, payload, status_code=200):
    content_length = len(payload)
    send_header(client, status_code, content_length)
    if content_length > 0:
        client.sendall(payload)
    client.close()


def handle_root(client):
    try:
        wlan_sta.active(True)
        ssids = sorted(ssid.decode('utf-8') for ssid, *_ in wlan_sta.scan())
        send_header(client)
        client.sendall("""\
            <html>
                <head>
                    <meta name="viewport" content="initial-scale=1.0, width=device-width">
                    <style>
                        a,abbr,acronym,address,applet,article,aside,audio,b,big,blockquote,body,canvas,caption,center,cite,code,dd,del,details,dfn,div,dl,dt,em,embed,fieldset,figcaption,figure,footer,form,h1,h2,h3,h4,h5,h6,header,hgroup,html,i,iframe,img,ins,kbd,label,legend,li,mark,menu,nav,object,ol,output,p,pre,q,ruby,s,samp,section,small,span,strike,strong,sub,summary,sup,table,tbody,td,tfoot,th,thead,time,tr,tt,u,ul,var,video{margin:0;padding:0;border:0;font:inherit;vertical-align:baseline}article,aside,details,figcaption,figure,footer,header,hgroup,menu,nav,section{display:block}ol,ul{list-style:none}blockquote,q{quotes:none}blockquote:after,blockquote:before,q:after,q:before{content:'';content:none}table{border-collapse:collapse;border-spacing:0}*{text-rendering:geometricPrecision;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale}html{font-size:62.5%}@media screen and (min-width:768px){html{font-size:75%}}body{font-family:"Source Sans Pro",Verdana,Geneva,sans-serif;color:#3c3c3d;font-size:1.5rem;line-height:1.44}h1,h2,h3{font-family:"PT Sans",Futura,"Trebuchet MS",Arial,sans-serif;letter-spacing:1px;font-weight:700}code,kbd,pre,samp{font-family:"PT Mono",monospace;background-color:#efeff0;border:1px solid #dededf;border-radius:2px;font-size:1.3rem}code,kbd,samp{padding:0 4px}pre{padding:8px}pre code,pre kbd,pre samp{background-color:transparent;border:none;border-radius:0;padding:0}h1,h2,h3,h4,h5,h6{padding:13px 0 21px;line-height:1.2}@media screen and (min-width:768px){h1,h2,h3,h4,h5,h6{padding-bottom:21px 0 34px}}h1:first-child,h2:first-child,h3:first-child,h4:first-child,h5:first-child,h6:first-child{padding-top:0}h1{font-size:3.4rem;font-weight:700}h2{font-size:2.8rem}h3{font-size:2.4rem}h4{font-size:2rem;font-weight:700}h5{font-size:2rem;font-weight:400}h6{font-size:2rem;font-style:italic}a:link{color:#216a9e;text-decoration:underline}a:visited{color:purple}a:focus,a:hover{color:#184f74}a:active{color:#2a89c8}img{max-width:100%}blockquote,hr,pre{margin-bottom:13px}@media screen and (min-width:768px){blockquote,hr,pre{margin-bottom:21px}}dd,dl,figcaption,figure,img,ol,p,ul{padding-bottom:13px}@media screen and (min-width:768px){dd,dl,figcaption,figure,img,ol,p,ul{padding-bottom:21px}}hr{border-top:1px solid #cdcdce;border-bottom:1px solid #efeff0;border-left:none;border-right:none}blockquote{margin-left:13px;border-left:3px solid #cdcdce;padding:8px 13px}@media screen and (min-width:768px){blockquote{margin-left:21px;border-left:5px solid #cdcdce;padding:13px 21px}}blockquote p:last-child{padding-bottom:0}ol,ul{margin-left:21px}@media screen and (min-width:768px){ol,ul{margin-left:34px}}ol{list-style-type:decimal}ul{list-style-type:disc}dt{font-style:italic}dd{text-indent:21px}@media screen and (min-width:768px){dd{text-indent:34px}}figure{display:table;margin:0 auto;padding-left:13px;padding-right:13px}@media screen and (min-width:768px){figure{padding-left:21px;padding-right:21px}}figure img{display:table;margin:0 auto}figcaption,small,sub,sup{font-size:1.3rem}caption,figcaption{text-align:center;font-style:italic}cite,em,i{font-style:italic}b,strong,var{font-weight:700}q:after,q:before{content:"'"}q>q{font-style:italic}abbr,dfn{border-bottom:1px dotted #7d7d7e;cursor:default}sub{vertical-align:sub}sup{vertical-align:super}table{margin:0 auto}table caption{margin-bottom:5px}table thead{background-color:#216a9e;color:#fff}table tbody{background-color:#efeff0}table tbody tr:nth-child(2n){background-color:#dededf}table td,table th{padding:5px 8px}@media screen and (min-width:768px){table td,table th{padding:8px 13px}}table tfoot{background-color:#cdcdce}table tfoot td{text-align:center}
                        td { padding: 10px 20px; font-size: 1.4rem; }
                        .button { paddiong: 10px 20px; font-size: 1.6rem;}
                    </style>
                </head>
                <body>
                <h1 style="color: #5e9ca0; text-align: center;">
                    <span style="color: #ff0000;">
                        Wi-Fi Client Setup
                    </span>
                </h1>
                <form action="configure" method="post">
                    <table style="margin-left: auto; margin-right: auto;">
                        <tbody>
        """)
        while len(ssids):
            ssid = ssids.pop(0)
            client.sendall(f"""\
                            <tr>
                                <td colspan="2">
                                    <input type="radio" name="ssid" value="{ssid}" /><label for="{ssid}">{ssid}</label>
                                </td>
                            </tr>
            """)
        client.sendall("""\
                            <tr>
                                <td><label for="password">Password:</label></td>
                                <td><input name="password" type="password" /></td>
                            </tr>
                        </tbody>
                    </table>
                    <p style="text-align: center;">
                        <input type="submit" value="Submit" class="button" />
                    </p>
                </form>
                </body>
            </html>
        """)
        client.close()
    except Exception as e:
        if e.errno == errno.ECONNRESET:
            pass
        else:
            raise

def handle_configure(client, request):
    match = ure.search("ssid=([^&]*)&password=(.*)", request)

    if match is None:
        send_response(client, "Parameters not found", status_code=400)
        return False
    # version 1.9 compatibility
    try:
        ssid = match.group(1).decode("utf-8").replace("%3F", "?").replace("%21", "!").replace("+"," ").replace("%26", "&")
        password = match.group(2).decode("utf-8").replace("%3F", "?").replace("%21", "!").replace("%26", "&")
    except Exception:
        ssid = match.group(1).replace("%3F", "?").replace("%21", "!").replace("+"," ").replace("%26", "&")
        password = match.group(2).replace("%3F", "?").replace("%21", "!").replace("%26", "&")

    if len(ssid) == 0:
        send_response(client, "SSID must be provided", status_code=400)
        return False

    if do_connect(ssid, password):
        response = """\
            <html>
                <center>
                    <br><br>
                    <h1 style="color: #5e9ca0; text-align: center;">
                        <span style="color: #ff0000;">
                            ESP successfully connected to WiFi network %(ssid)s.
                        </span>
                    </h1>
                    <br><br>
                </center>
            </html>
        """ % dict(ssid=ssid)
        send_response(client, response)
        try:
            profiles = read_profiles()
        except OSError:
            profiles = {}
        profiles[ssid] = password
        write_profiles(profiles)

        time.sleep(5)

        return True
    else:
        response = """\
            <html>
                <center>
                    <h1 style="color: #5e9ca0; text-align: center;">
                        <span style="color: #ff0000;">
                            ESP could not connect to WiFi network %(ssid)s.
                        </span>
                    </h1>
                    <br><br>
                    <form>
                        <input type="button" value="Go back!" onclick="history.back()"></input>
                    </form>
                </center>
            </html>
        """ % dict(ssid=ssid)
        send_response(client, response)
        return False