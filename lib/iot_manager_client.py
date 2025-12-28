"""
    IoT Manager MicroPython Client.
"""
import gc
import uos
import urequests as requests
import ujson as json
import ubinascii as binascii
import deflate
import lib.utarfile as tarfile
import time
import machine


class IotManagerError(Exception):
    pass


class AuthenticationError(IotManagerError):
    pass


class EndpointNotFoundError(IotManagerError):
    pass


class ServerError(IotManagerError):
    pass


def _join_url(base_url, path):
    base = base_url.rstrip('/')
    url_without_path = "/".join(base.split("/")[:-1])
    if not path:
        return url_without_path
    if path.startswith('/'):
        return url_without_path + path
    return url_without_path + '/' + path


def _encode_qs(params):
    if not params:
        return ''
    parts = []
    for k, v in params.items():
        if v is None:
            continue
        parts.append("%s=%s" % (str(k), str(v)))
    return '&'.join(parts)


def _generate_boundary():
    """Generate a boundary string for multipart form data."""
    try:
        import os
        random_bytes = os.urandom(8)
    except (ImportError, NotImplementedError):
        # Fallback for systems without os.urandom
        import time
        random_bytes = str(int(time.time() * 1000000))[-8:].encode()
    
    return 'boundary' + binascii.hexlify(random_bytes).decode()


def _encode_multipart_form_data(fields, files=None):
    """Encode form data and files as multipart/form-data.
    
    Args:
        fields: dict of field_name -> value for regular form fields
        files: dict of field_name -> {'filename': str, 'content': bytes, 'content_type': str}
    
    Returns:
        tuple: (body_bytes, content_type_header)
    """
    boundary = _generate_boundary()
    lines = []
    
    # Add regular fields
    if fields:
        for name, value in fields.items():
            lines.append('--' + boundary)
            lines.append('Content-Disposition: form-data; name="%s"' % name)
            lines.append('')
            lines.append(str(value))
    
    # Add file fields
    if files:
        for field_name, file_info in files.items():
            lines.append('--' + boundary)
            filename = file_info.get('filename', 'file')
            content_type = file_info.get('content_type', 'application/octet-stream')
            lines.append('Content-Disposition: form-data; name="%s"; filename="%s"' % (field_name, filename))
            lines.append('Content-Type: %s' % content_type)
            lines.append('')
            lines.append('__BINARY_CONTENT_%s__' % field_name)
    
    lines.append('--' + boundary + '--')
    lines.append('')
    
    # Create the body with proper binary handling
    body_parts = []
    text_body = '\r\n'.join(lines)
    
    if files:
        # Split and rebuild with binary content
        for field_name, file_info in files.items():
            placeholder = '__BINARY_CONTENT_%s__' % field_name
            if placeholder in text_body:
                parts = text_body.split(placeholder)
                body_parts.append(parts[0].encode('utf-8'))
                body_parts.append(file_info['content'])
                text_body = placeholder.join(parts[1:])  # Remaining parts
        
        # Add final part
        if text_body:
            body_parts.append(text_body.encode('utf-8'))
    else:
        body_parts.append(text_body.encode('utf-8'))
    
    # Combine all parts
    body = b''
    for part in body_parts:
        if isinstance(part, str):
            body += part.encode('utf-8')
        else:
            body += part
    
    content_type = 'multipart/form-data; boundary=' + boundary
    return body, content_type


class IotManagerClient:
    """MicroPython client for IoT Manager servers."""
    def __init__(self, base_url, authorization=None, timeout_s=10, auto_discover=False):
        if(authorization is None and auto_discover):
            raise ValueError("Authorization must be provided if auto_discover is True")
        
        self.base_url = base_url.rstrip('/')
        self.authorization = authorization
        self.timeout_s = timeout_s

        self._endpoints = {} 
        self._available_methods = []
        if auto_discover:
            self.discover()

    def discover(self):
        data = self._request_raw('GET', self.base_url)
        endpoints = data.get('endpoints', []) if isinstance(data, dict) else []

        self._endpoints = {}
        self._available_methods = []

        for ep in endpoints:
            desc = ep.get('description', '')
            method = (ep.get('method', '') or '').upper()
            path = ep.get('path', '')
            self._endpoints[desc] = {
                'method': method,
                'path': path,
                'url': _join_url(self.base_url, path),
            }
            m = self._description_to_method_name(desc)
            if m:
                self._available_methods.append(m)
        return data

    def get_available_methods(self):
        return list(self._available_methods)

    def get_endpoints_info(self):
        return dict(self._endpoints)

    def _description_to_method_name(self, description):
        mapping = {
            'GetLatestVersion': 'get_latest_version',
            'CreateDeviceStatus': 'create_device_status',
            'CreateContent': 'create_content',
            'Authenticate': 'authenticate',
            'GetConfig': 'get_config',
        }
        return mapping.get(description)

    def _method_name_to_description(self, method_name):
        rev = {
            'get_latest_version': 'GetLatestVersion',
            'create_device_status': 'CreateDeviceStatus',
            'create_content': 'CreateContent',
            'authenticate': 'Authenticate',
            'get_config': 'GetConfig',
        }
        return rev.get(method_name)

    def _headers(self, extra=None, json_body=False):
        h = {
            'Accept': 'application/json',
        }
        if self.authorization:
            h['Authorization'] = self.authorization
        if json_body:
            h['Content-Type'] = 'application/json'
        if extra:
            h.update(extra)
        return h

    def _request_raw(self, method, url, params=None, json_body=None, multipart_data=None):
        """Return parsed JSON dict/list (or raise)."""
        gc.collect()
        if params and method.upper() == 'GET':
            qs = _encode_qs(params)
            if qs:
                url = url + ('&' if '?' in url else '?') + qs

        body = None
        headers = None
        if multipart_data is not None:
            fields = multipart_data.get('fields', {})
            files = multipart_data.get('files', {})
            body, content_type = _encode_multipart_form_data(fields, files)
            headers = self._headers(extra={'Content-Type': content_type})
        elif json_body is not None:
            body = json.dumps(json_body)
            headers = self._headers(json_body=True)
        else:
            headers = self._headers()

        resp = None
        try:
            if method.upper() == 'GET':
                resp = requests.get(url, headers=headers)
            elif method.upper() == 'POST':
                resp = requests.post(url, data=body, headers=headers)
            else:
                raise IotManagerError('Unsupported HTTP method: %s' % method)

            status = getattr(resp, 'status_code', None)
            print("Response status:", status)
            if status is None:
                status = resp.status

            if status == 401:
                raise AuthenticationError('Authentication failed')
            if status == 403:
                raise AuthenticationError('Access forbidden')
            if status < 200 or status >= 300:
                # Try to parse error body
                try:
                    err = resp.json()
                    if isinstance(err, dict) and 'error' in err:
                        raise ServerError('Server returned %d: %s' % (status, err.get('error')))
                except Exception:
                    pass
                raise ServerError('Server returned %d' % status)

            try:
                return resp.json()
            except Exception:
                txt = resp.text
                if not txt:
                    return {}
                return json.loads(txt)
        finally:
            try:
                if resp is not None:
                    resp.close()
            except Exception:
                pass

    def _call_discovered(self, method_name, data=None, params=None, multipart_data=None):
        desc = self._method_name_to_description(method_name)
        if not desc or desc not in self._endpoints:
            raise EndpointNotFoundError('Method not available: %s' % method_name)

        ep = self._endpoints[desc]
        http_method = ep['method']
        url = ep['url']

        if http_method == 'GET':
            return self._request_raw('GET', url, params=params)
        if http_method == 'POST':
            return self._request_raw('POST', url, json_body=data, multipart_data=multipart_data)
        raise IotManagerError('Unsupported HTTP method: %s' % http_method)
    
    def check_and_update_firmware(self):
        ota_updater = OTAUpdater(self)
        return ota_updater.check_and_perform_update()


    def get_config(self, **params):
        return self._call_discovered('get_config', params=params)

    def get_latest_version(self, **params):
        return self._call_discovered('get_latest_version', params=params)

    def create_device_status(self, status_obj):
        return self._call_discovered('create_device_status', data=status_obj)

    def create_content(self, content_obj=None, files=None, **fields):
        """Create content on the server.
        
        Args:
            content_obj: JSON data to send (traditional usage)
            files: dict of field_name -> {'filename': str, 'content': bytes, 'content_type': str}
                   for file uploads (e.g., JPEG images)
            **fields: additional form fields for multipart uploads
        
        Example:
            # Traditional JSON usage
            client.create_content({"key": "value"})
            
            # Multipart form with JPEG image
            with open('image.jpg', 'rb') as f:
                image_data = f.read()
            
            client.create_content(
                files={
                    'image': {
                        'filename': 'photo.jpg',
                        'content': image_data,
                        'content_type': 'image/jpeg'
                    }
                },
                description="My photo",
                deviceId="esp32-001"
            )
        """
        if files or fields:
            # Use multipart form data
            multipart_data = {
                'fields': fields,
                'files': files or {}
            }
            return self._call_discovered('create_content', multipart_data=multipart_data)
        else:
            # Use traditional JSON
            return self._call_discovered('create_content', data=content_obj)

    def upload_image(self, image_data, filename=None, device_id=None, description=None, test_post=False, **extra_fields):
        """Convenience method to upload a JPEG image.
        
        Args:
            image_data: bytes of the JPEG image
            filename: optional filename (defaults to 'image.jpg')
            device_id: optional device ID
            description: optional description
            **extra_fields: additional form fields
        
        Returns:
            Server response
        """
        if not filename:
            filename = 'image.jpg'
        
        files = {
            'image': {
                'filename': filename,
                'content': image_data,
                'content_type': 'image/jpeg'
            }
        }
        
        fields = {}
        if device_id:
            fields['deviceId'] = device_id
        if description:
            fields['description'] = description
        if test_post:
            fields['testPost'] = 'true'
        fields.update(extra_fields)
        
        return self.create_content(files=files, **fields)

    def authenticate(self, device_id, password):
        payload = {"deviceId": device_id, "password": password}
        print("requesting authentication for device_id:", device_id)
        result = self._request_raw('POST', self.base_url + '/authenticate', json_body=payload)
        if not isinstance(result, dict) or 'authorization' not in result:
            raise ServerError('Authenticate did not return authorization')
        self.authorization = result['authorization']
        return self.authorization


class OTAUpdater:
    """Over-the-air updater using IoT Manager."""
    def __init__(self, client: IotManagerClient):
        self.client = client

    def _normalize_tar_path(self, tar_name: str):
        if not tar_name:
            return None

        name = tar_name.replace('\\', '/')
        while name.startswith('./'):
            name = name[2:]
        while name.startswith('/'):
            name = name[1:]

        if name == '' or name == '.' or name.startswith('../') or '/..' in name:
            return None

        # Keep already-rooted firmware paths
        if name == 'main.py' or name.startswith('lib/'):
            return name

        # If packaged with a top-level directory, strip exactly one component
        if '/' in name:
            _, remainder = name.split('/', 1)
            if remainder == 'main.py' or remainder.startswith('lib/'):
                return remainder

        return None

    def _ensure_parent_dirs(self, rel_path: str):
        if not rel_path or '/' not in rel_path:
            return
        parts = rel_path.split('/')[:-1]
        acc = ''
        for part in parts:
            if not part:
                continue
            acc = part if not acc else acc + '/' + part
            try:
                uos.mkdir(acc)
            except OSError as e:
                if getattr(e, 'errno', None) == 17:
                    pass
                else:
                    try:
                        uos.stat(acc)
                    except Exception:
                        raise

    def get_current_version(self):
        try:
            with open('version.dat', 'r') as f:
                version = f.read().strip()
                return version
        except Exception:
            return None

    def check_for_update(self):
        data = self.client.get_latest_version()
        latest_version = data.get('version')
        download_url = data.get('url')
        print("Latest version:", latest_version, "Download URL:", download_url)
        current_version = self.get_current_version()
        print("Current version:", current_version)
        if latest_version and download_url:
            if latest_version != current_version:
                return latest_version, download_url
        return None, None

    def check_and_perform_update(self):
        tmp_filename = '/ota_version.tmp'
        gc.collect()
        latest_version, download_url = self.check_for_update()
        if latest_version and download_url:
            print(f"Updating to {latest_version}, downloading from {download_url} ...")
            response = requests.get(download_url, headers={"User-Agent": "TimeLapseCam Agent"}, stream=True)
            print("Download response status:", response.status_code)
            with open(tmp_filename, 'wb') as f:
                print("Writing to temporary file:", tmp_filename)
                while True:
                    chunk = response.raw.read(512)
                    print("Downloaded chunk size:", len(chunk))
                    if not chunk:
                        break
                    f.write(chunk)
                    print("Wrote chunk to file.")
            
            gc.collect()
            try:
                uos.stat(tmp_filename)
            except OSError:
                print('No new firmware file found in flash.')
                return
            with open(tmp_filename, 'rb') as f1:
                f2 = deflate.DeflateIO(f1, deflate.GZIP)
                f3 = tarfile.TarFile(fileobj=f2)
                for _file in f3:
                    raw_name = getattr(_file, 'name', None)
                    file_name = self._normalize_tar_path(raw_name)
                    print(f'Extracting file: {raw_name} -> {file_name} ... ')
                    if not file_name:
                        continue

                    # Directory entries (some tars include them)
                    if file_name.endswith('/'):
                        dir_name = file_name[:-1]
                        if dir_name:
                            try:
                                uos.mkdir(dir_name)
                            except OSError as e:
                                if getattr(e, 'errno', None) != 17:
                                    try:
                                        uos.stat(dir_name)
                                    except Exception:
                                        raise
                        continue

                    self._ensure_parent_dirs(file_name)
                    file_obj = f3.extractfile(_file)
                    with open(file_name, 'wb') as f_out:
                        written_bytes = 0
                        while True:
                            buf = file_obj.read(512)
                            if not buf:
                                break
                            written_bytes += f_out.write(buf)
                        print(f'file {file_name} ({written_bytes} B) written to flash')

            print("Deleting temporary file:", tmp_filename)
            uos.remove(tmp_filename)

            print("Update applied successfully. write new version file.")
            with open('version.dat', 'w') as f:
                f.write(latest_version)
            print("Restarting device to apply update...")
            time.sleep(2)
            machine.reset()
        print("No update available.")
        return False