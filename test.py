import json
import socket
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


# with open('config.json') as f:
#    data = json.load(f)

# print(data["HTTPInjection"])

sock1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

proxy_port = 8080
proxy_ip = "127.0.0.1"

server_address = (proxy_ip, proxy_port)
print('starting up on %s port %s' % server_address)

# sock1.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

sock1.bind(server_address)

""" tu terminal bezan: ps -fA | grep python
    adade dovom o kill kon
"""

sock1.listen()


# Wait for a connection
print('waiting for a connection')
connection, client_address = sock1.accept()
print('connection from', client_address)
        # Receive the data in small chunks and retransmit it
connection.setblocking(0)
while True:
            req_from_browser = recv_all(connection)
            if not req_from_browser:
                print('no more data from', client_address)
                break
            req_from_browser_str = req_from_browser.decode('utf-8', 'ignore')
            print(req_from_browser_str)
            req_from_browser_list = req_from_browser_str.split('\r\n')
            req_line = req_from_browser_list[0]
            #initialize a dictionary for parsing a request
            req_header_dict = {}
            for i in range(1, len(req_from_browser_list)-2):
                key_name = req_from_browser_list[i].split(': ')[0]
                value = req_from_browser_list[i].split(': ')[1]
                req_header_dict[key_name] = value
            req_header_dict['Accept-Encoding'] = 'deflate'
            req_line_str = req_line.split()
            method = req_line_str[0]
            address = req_line_str[1]
            new_address = address[7+len(req_header_dict['Host']):]
            http_version = 'HTTP/1.0'
            final_req_line_proxy = method + ' ' + new_address + ' ' + http_version
            #prepare the request_to_internet
            req_to_internet = ""
            req_to_internet += final_req_line_proxy+'\r\n'
            for key, value in req_header_dict.items():
                head_temp = key + ': ' + value + '\r\n'
                req_to_internet += head_temp
            req_to_internet += '\r\n'
            print(req_to_internet)
            # print('received "%s"' % data)

            # connection.send(req_to_internet.encode())
            print('sending request to the internet')
            sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            internet_port = 80
            internet_ip = socket.gethostbyname(req_header_dict['Host'])
            sock2.connect((internet_ip, internet_port))
            sock2.send(req_to_internet.encode('ascii', 'ignore'))
            data = recv_all(sock2)
            print(data)
            connection.send(data)
            sock2.close()
                # connection.sendall(req_to_internet.encode('utf-8', 'ignore'))

connection.close()


