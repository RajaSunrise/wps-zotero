#!/usr/bin/env python3

import socket
import select
import sys
import logging
import os
import atexit
import traceback
import errno


ZOTERO_PORT = 23119
PROXY_PORT = 21931
BUFSIZE = 8192
DELAY = 0.0001
SOCKET_TIMEOUT = 5.0  # Seconds
PREFLIGHT_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS,PUT,PATCH,DELETE',
    'Access-Control-Allow-Headers': '*',
    'Access-Control-Allow-Credentials': 'true',
}


def parse_head(hd_raw):
    try:
        head = hd_raw.decode('utf8').split("\r\n")
    except UnicodeDecodeError:
        # Fallback to latin-1 if utf8 fails
        head = hd_raw.decode('latin-1').split("\r\n")

    request = head[0]
    headers = {}
    for line in head[1:]:
        if not line:
            continue
        # Split by first colon only
        parts = line.split(':', 1)
        if len(parts) == 2:
            key = parts[0].strip()
            # We don't change case of key here, but handle lookup case-insensitively
            headers[key] = parts[1].strip()

    return request, headers


def get_header(headers, key):
    """Case-insensitive header lookup"""
    key_lower = key.lower()
    for k, v in headers.items():
        if k.lower() == key_lower:
            return v
    return None


def recv_all(sock):
    data = b''
    closed = False

    # Read in Http head
    while True:
        try:
            part = sock.recv(BUFSIZE)
        except (ConnectionResetError, socket.timeout):
            closed = True
            break
        except BlockingIOError:
            break

        if not part:
            closed = True
            break
        data += part
        if b'\r\n\r\n' in data:
            break

    if not data:
        return data

    hd_raw = data.partition(b'\r\n\r\n')[0]
    req, headers = parse_head(hd_raw)

    # Read full body
    content_length = get_header(headers, 'Content-Length')
    if content_length:
        length = len(hd_raw) + 4 + int(content_length)
        while len(data) < length:
            try:
                part = sock.recv(BUFSIZE)
                if not part:
                    closed = True
                    break
                data += part
            except (ConnectionResetError, socket.timeout):
                closed = True
                break
    elif not closed:
        # No Content-Length.
        is_request = not req.startswith('HTTP/')
        expect_body = True

        if is_request:
            method = req.split(' ')[0].upper()
            if method in ['GET', 'HEAD', 'OPTIONS', 'TRACE', 'DELETE']:
                expect_body = False

        if expect_body:
            # Read until close
            while True:
                try:
                    part = sock.recv(BUFSIZE)
                    if not part:
                        closed = True
                        break
                    data += part
                except socket.timeout:
                    closed = True
                    break
                except ConnectionResetError:
                    closed = True
                    break

    return data


def stop_proxy():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(1.0)
        s.connect(('127.0.0.1', PROXY_PORT))
        s.send(b'POST /stopproxy HTTP/1.1\r\n\r\n')
    except Exception as e:
        print(f"Failed to stop proxy: {e}")
    finally:
        s.close()


class ProxyServer:
    input_list = []
    channels = {}
    clients = []

    def __init__(self, host, port, persistent=False):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.persistent = persistent
        # NOTE: Setting this on Windows will cause multiple instances listening on the same port.
        if os.name == 'posix':
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((host, port))
        self.server.listen()
        self.running = False

    def run(self):
        self.input_list.append(self.server)
        self.running = True
        mode = "persistent" if self.persistent else "normal"
        print(f"Proxy server running on {PROXY_PORT} (mode: {mode})...")
        while self.running:
            try:
                # Use a timeout in select to allow catching KeyboardInterrupt immediately
                rlist, _, _ = select.select(self.input_list, [], [], 1.0)
            except (KeyboardInterrupt, InterruptedError):
                print("Stopping proxy server...")
                self.running = False
                break
            except Exception as e:
                logging.error(f"Select error: {e}")
                break

            for s in rlist:
                if s == self.server:
                    self.on_accept()
                    break

                try:
                    data = recv_all(s)
                except Exception as e:
                    logging.error("Error receiving data: {}".format(e))
                    self.on_close(s)
                    continue

                if len(data) == 0:
                    self.on_close(s)
                else:
                    self.on_recv(s, data)

        # Close all sockets
        for s in self.input_list:
            try:
                s.close()
            except Exception as e:
                logging.error(f"Failed to close socket: {e}")
        self.input_list.clear()
        self.channels.clear()
        self.clients.clear()
        try:
            self.server.close()
        except Exception as e:
            logging.error(f"Failed to close server: {e}")

    def on_accept(self):
        try:
            clientsock, clientaddr = self.server.accept()
        except Exception as e:
            logging.error(f"Accept error: {e}")
            return

        # Set timeout to prevent hanging on recv
        clientsock.settimeout(SOCKET_TIMEOUT)

        self.clients.append(clientaddr)
        self.input_list.append(clientsock)
        logging.info("{} has connected".format(clientaddr))
        forward = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            forward.settimeout(SOCKET_TIMEOUT)
            forward.connect(('127.0.0.1', ZOTERO_PORT))
        except socket.error as e:
            logging.warning("Cannot connect to Zotero, is the app started?")
            logging.debug("Failed to connect to Zotero: {}".format(e))
            forward.close()
            # Respond with 503
            try:
                response = b'HTTP/1.1 503 Service Unavailable\r\nContent-Type: text/plain\r\n\r\nZotero is not running.'
                clientsock.send(response)
                clientsock.close()
            except Exception as e:
                logging.error(f"Failed to send response: {e}")

            if clientsock in self.input_list:
                self.input_list.remove(clientsock)
            if clientaddr in self.clients:
                self.clients.remove(clientaddr)

            return

        self.input_list.append(forward)
        self.channels[clientsock] = forward
        self.channels[forward] = clientsock

    def on_close(self, s):
        try:
            pname = s.getpeername()
        except Exception as e:
            logging.error(f"Failed to get peer name: {e}")
            pname = "unknown"

        if pname in self.clients:
            try:
                self.clients.pop(self.clients.index(pname))
            except ValueError:
                pass

        if s in self.channels:
            out = self.channels[s]
            try:
                out.close()
            except Exception as e:
                logging.error(f"Failed to close channel: {e}")
            if out in self.input_list:
                self.input_list.remove(out)
            del self.channels[s]
            try:
                del self.channels[out]
            except KeyError:
                pass

        if s in self.input_list:
            self.input_list.remove(s)
        try:
            s.close()
        except Exception as e:
            logging.error(f"Failed to close socket: {e}")
        logging.info("{} has disconnected".format(pname))

    def on_recv(self, s, data):
        # logging.debug('received data: {}'.format(data))
        if data.startswith(b'POST /stopproxy'):
            logging.info('received stopping command!')
            if self.persistent:
                logging.info('Persistent mode enabled: ignoring stop command.')
                # Send 200 OK so the caller knows we received it, but we don't stop.
                try:
                    s.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n')
                except Exception as e:
                    logging.error(f"Failed to send response: {e}")
                # We don't close socket immediately, or maybe we do?
                # Usually HTTP is request-response.
            else:
                s.close()
                self.running = False
            return

        if s not in self.channels:
            self.on_close(s)
            return

        # Parse HEAD
        head_raw, _, body_raw = data.partition(b"\r\n\r\n")
        try:
            request, headers = parse_head(head_raw)
        except Exception as e:
            logging.error("Failed to parse header: {}".format(e))
            self.on_close(s)
            return

        try:
            peer_name = s.getpeername()
        except Exception as e:
            logging.error(f"Failed to get peer name: {e}")
            peer_name = None

        if peer_name in self.clients:
            # Preflight responses
            logging.info('message received on client {}'.format(peer_name))
            if data.startswith(b'OPTIONS') and get_header(headers, 'Origin') and get_header(headers, 'Access-Control-Request-Method'):
                for k,v in PREFLIGHT_HEADERS.items():
                    headers[k] = v

                response_headers = []
                for k,v in headers.items():
                    response_headers.append(f"{k}: {v}")

                # Preflight response
                data = ('HTTP/1.1 200 OK\r\n' + '\r\n'.join(response_headers) + '\r\n\r\n').encode('utf8') + body_raw
                try:
                    s.sendall(data)
                except Exception as e:
                    logging.error(f"Failed to send preflight response: {e}")
                logging.info('responded to a preflight request')
                return

            # Forwarding request to Zotero
            headers['Host'] = '127.0.0.1:{}'.format(ZOTERO_PORT)

            # Force close connection so we don't have to deal with Keep-Alive
            headers['Connection'] = 'close'

            # Reconstruct headers
            header_lines = []
            for k,v in headers.items():
                header_lines.append(f"{k}: {v}")

            data = (request + '\r\n' + '\r\n'.join(header_lines) + '\r\n\r\n').encode('utf8') + body_raw

        else:
            logging.info('message received from zotero')
            # CORS
            headers['Access-Control-Allow-Origin'] = '*'

            header_lines = []
            for k,v in headers.items():
                header_lines.append(f"{k}: {v}")

            data = (request + '\r\n' + '\r\n'.join(header_lines) + '\r\n\r\n').encode('utf8') + body_raw

        try:
            self.channels[s].send(data)
            # logging.info('responded to {}'.format(self.channels[s].getpeername()))
        except Exception as e:
            logging.error("Failed to send data: {}".format(e))
            self.on_close(s)


def main(argv):
    # Configure logging
    if os.name == 'posix':
        logfile = os.environ['HOME'] + '/.wps-zotero-proxy.log'
    else:
        logfile = os.environ['APPDATA'] + '\\kingsoft\\wps\\jsaddons\\wps-zotero-proxy.log'

    # Rotate log if too big
    if os.path.exists(logfile) and os.path.getsize(logfile) > 100 * 1024:
        try:
            os.remove(logfile)
        except Exception as e:
            logging.error(f"Failed to remove log file: {e}")

    logging.basicConfig(filename=logfile,
                        filemode='a',
                        format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s: %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    # Check for arguments
    persistent = False
    if '--persistent' in argv:
        persistent = True
    elif len(argv) > 1 and argv[1] == 'kill':
        stop_proxy()
        return

    try:
        server = ProxyServer('127.0.0.1', PROXY_PORT, persistent=persistent)
        logging.info('proxy started!')
        atexit.register(lambda : logging.info('proxy stopped!'))
        server.run()
    except (KeyboardInterrupt, SystemExit):
        logging.info("Proxy stopped by user.")
    except Exception as e:
        if isinstance(e, socket.error) and e.errno == errno.EADDRINUSE:
            logging.warning("port is already binded!")
            # On Windows, we might want to kill existing? But that's dangerous.
            # Just exit.
            sys.exit()
        else:
            logging.error('encountered unexpected error, exiting!')
            logging.error(e)
            logging.error(traceback.format_exc())


if __name__ == '__main__':
    main(sys.argv)
