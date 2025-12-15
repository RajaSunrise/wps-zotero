#!/usr/bin/env python3

import socket
import select
import time
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
        except ConnectionResetError:
            closed = True
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
            except ConnectionResetError:
                closed = True
                break
    elif not closed:
        if req.startswith('TRACE'):
            # TRACE method must not include a body
            pass
        elif data.startswith(b'OPTIONS') and get_header(headers, 'Origin') and get_header(headers, 'Access-Control-Request-Method'):
            # Preflight requests don't have a body
            pass
        else:
            # Continue to read till the connection is closed
            # Or if Content-Length is missing and it's not one of above, we might just assume end of request if we can't determine.
            # But for HTTP/1.1 without Content-Length or Chunked, it usually means no body or close connection.
            # For this proxy, we might get stuck here if we just wait for close.
            # However, Zotero plugin communication usually has Content-Length for POST.
            pass

    return data


def stop_proxy():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(('127.0.0.1', PROXY_PORT))
        s.send(b'POST /stopproxy HTTP/1.1\r\n\r\n')
    except:
        # Swallow all exceptions
        pass
    finally:
        s.close()


class ProxyServer:
    input_list = []
    channels = {}
    clients = []

    def __init__(self, host, port):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # NOTE: Setting this on Windows will cause multiple instances listening on the same port.
        if os.name == 'posix':
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1);
        self.server.bind((host, port))
        self.server.listen()
        self.running = False

    def run(self):
        self.input_list.append(self.server)
        self.running = True
        while self.running:
            time.sleep(DELAY)
            rlist, _, _ = select.select(self.input_list, [], [])
            for s in rlist:
                if s == self.server:
                    self.on_accept()
                    break

                try:
                    data = recv_all(s)
                except Exception as e:
                    logging.error("Error receiving data: {}".format(e))
                    self.on_close(s)
                    break

                if len(data) == 0:
                    self.on_close(s)
                    break
                else:
                    self.on_recv(s, data)

        # Close all sockets
        for s in self.input_list:
            try:
                s.close()
            except:
                pass
        self.input_list.clear()
        self.channels.clear()
        self.clients.clear()
        self.server.close()

    def on_accept(self):
        clientsock, clientaddr = self.server.accept()
        self.clients.append(clientaddr)
        self.input_list.append(clientsock)
        logging.info("{} has connected".format(clientaddr))
        forward = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            forward.connect(('127.0.0.1', ZOTERO_PORT))
        except socket.error as e:
            logging.warning("Cannot connect to Zotero, is the app started?")
            logging.debug("Failed to connect to Zotero: {}".format(e))
            forward.close()
            # NOTE: Cannot close client sockets here for it will discard quit commands.
            # But we should probably send an error response to client so it knows Zotero is down.

            # Simple 503 Service Unavailable
            response = b'HTTP/1.1 503 Service Unavailable\r\nContent-Type: text/plain\r\n\r\nZotero is not running.'
            clientsock.send(response)
            clientsock.close()
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
        except:
            pname = "unknown"

        if pname in self.clients:
            self.clients.pop(self.clients.index(pname))
        if s in self.channels:
            out = self.channels[s]
            try:
                out.close()
            except:
                pass
            if out in self.input_list:
                self.input_list.remove(out)
            del self.channels[s]
            del self.channels[out]
        if s in self.input_list:
            self.input_list.remove(s)
        try:
            s.close()
        except:
            pass
        logging.info("{} has disconnected".format(pname))

    def on_recv(self, s, data):
        # logging.debug('received data: {}'.format(data))
        if data.startswith(b'POST /stopproxy'):
            logging.info('received stopping command!')
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
        except:
            peer_name = None

        if peer_name in self.clients:
            # Preflight responses
            logging.info('message received on client {}'.format(peer_name))
            if data.startswith(b'OPTIONS') and get_header(headers, 'Origin') and get_header(headers, 'Access-Control-Request-Method'):
                for k,v in PREFLIGHT_HEADERS.items():
                    headers[k] = v

                # Reconstruct headers with original case keys if possible, or just new ones
                response_headers = []
                for k,v in headers.items():
                    response_headers.append(f"{k}: {v}")

                data = ('HTTP/1.1 200 OK\r\n' + '\r\n'.join(response_headers) + '\r\n\r\n').encode('utf8') + body_raw
                s.sendall(data)
                logging.info('responded to a preflight request')
                return

            # Forwarding request to Zotero
            # Rewrite Host header to match Zotero's port
            headers['Host'] = '127.0.0.1:{}'.format(ZOTERO_PORT)

            # Reconstruct data
            # We must reconstruct the request carefully.
            # data is bytes.

            # Rebuild headers
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
        except:
            pass

    logging.basicConfig(filename=logfile,
                        filemode='a',
                        format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s: %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    if len(argv) < 2:
        try:
            server = ProxyServer('127.0.0.1', PROXY_PORT)
            logging.info('proxy started!')
            atexit.register(lambda : logging.info('proxy stopped!'))
            server.run()
        except Exception as e:
            if isinstance(e, socket.error) and e.errno == errno.EADDRINUSE:
                logging.warning("port is already binded!")
                sys.exit()
            else:
                logging.error('encountered unexpected error, exiting!')
                logging.error(e)
                logging.error(traceback.format_exc())
    else:
        if (argv[1] == 'kill'):
            stop_proxy()


if __name__ == '__main__':
    main(sys.argv)
