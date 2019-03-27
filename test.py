import json
import socket
import threading
import time
import sys


def recv_all(target_socket):
    message = b''
    try:
        while True:
            chunk = target_socket.recv(1)
            # print(message)
            if not chunk:
                break
            message += chunk

    except Exception as err:
        return message
    return message


class ThreadedServer(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))

    def listen(self):
        self.sock.listen(5)
        while True:
            print('waiting for a connection')
            client, client_address = self.sock.accept()
            print('connection from', client_address)
            client.settimeout(60)
            threading.Thread(target=self.listenToClient, args=(client, client_address)).start()

    def listenToClient(self, client, client_address):
        client.setblocking(0)
        # size = 1024
        while True:
            try:
                req_from_browser = recv_all(client)
                if not req_from_browser:
                    print('no more data from', client_address)
                    raise Exception
                req_from_browser_str = req_from_browser.decode('utf-8', 'ignore')
                print("this is request from browser to proxy:")
                print(req_from_browser_str)
                req_from_browser_list = req_from_browser_str.split('\r\n')
                req_line = req_from_browser_list[0]
                # initialize a dictionary for parsing a request
                req_header_dict = {}
                for i in range(1, len(req_from_browser_list) - 2):
                    key_name = req_from_browser_list[i].split(': ')[0]
                    value = req_from_browser_list[i].split(': ')[1]
                    req_header_dict[key_name] = value
                # req_header_dict['Accept-Encoding'] = 'deflate'
                req_line_str = req_line.split()
                method = req_line_str[0]
                address = req_line_str[1]
                new_address = address[7 + len(req_header_dict['Host']):]
                http_version = 'HTTP/1.0'
                final_req_line_proxy = method + ' ' + new_address + ' ' + http_version
                # prepare the request_to_server
                req_to_server = ""
                req_to_server += final_req_line_proxy + '\r\n'
                for key, value in req_header_dict.items():
                    head_temp = key + ': ' + value + '\r\n'
                    req_to_server += head_temp
                req_to_server += '\r\n'
                print('this is request from proxy to the server:')
                print(req_to_server)
                # print('received "%s"' % data)
                # connection.send(req_to_server.encode())
                # print('sending request to the server')
                sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_port = 80
                server_ip = socket.gethostbyname(req_header_dict['Host'])
                sock2.connect((server_ip, server_port))
                sock2.send(req_to_server.encode('ascii', 'ignore'))
                # time.sleep(2)
                data = recv_all(sock2)
                print('this is response from the server to proxy')
                print(data)
                client.send(data)
                sock2.close()
                # connection.sendall(req_to_server.encode('utf-8', 'ignore'))
            except:
                client.close()
                return False


if __name__ == "__main__":
    proxy_port = 8080
    proxy_ip = "127.0.0.1"
    # proxy_address = (proxy_ip, proxy_port)
    # while True:
    #     port_num = input("Port? ")
    #     try:
    #         port_num = int(port_num)
    #         break
    #     except ValueError:
    #         pass

    ThreadedServer(proxy_ip, proxy_port).listen()
