import json
import socket
import threading
import logging
import ssl
import base64
import collections
from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime
from bs4 import BeautifulSoup


def isLineEmpty(line):
    return len(line.strip()) == 0


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


def parse_head_resp(head_resp):
    head_resp_dict = {}
    head_resp_list = head_resp.split('\r\n')
    for i in range(1, len(head_resp_list)):
        key_name = head_resp_list[i].split(': ')[0]
        value = head_resp_list[i].split(': ')[1]
        head_resp_dict[key_name] = value
    return head_resp_dict


class LRUCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self.cache = collections.OrderedDict()

    def get(self, key):
        try:
            value = self.cache.pop(key)
            self.cache[key] = value
            return value
        except KeyError:
            return -1

    def set(self, key, value):
        try:
            self.cache.pop(key)
        except KeyError:
            if len(self.cache) >= self.capacity:
                self.cache.popitem(last=False)
        self.cache[key] = value


class ThreadedServer(object):
    def __init__(self, host, port):
        logging.info('Proxy launched')
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        logging.info('Socket created')
        self.sock.bind((self.host, self.port))
        logging.info(f'Binding the socket to the port:{port} on localhost')


    def listen(self):
        self.sock.listen()
        logging.info('waiting for a connection')
        while True:
            client, client_address = self.sock.accept()
            logging.info(f'connection from {client_address}')
            # client.settimeout(60)
            threading.Thread(target=self.listenToClient, args=(client, client_address)).start()

    def listenToClient(self, client, client_address):
        # client.setblocking(0)
        client.settimeout(2)
        while True:
            try:
                req_from_browser = recv_all(client)
                if not req_from_browser:
                    # print('no more data from', client_address)
                    logging.info(f'no more data from {client_address}')
                    raise Exception
                req_from_browser_str = req_from_browser.decode('utf-8', 'ignore')
                logging.info('\n''----------------------------------------------------------------------\n'
                             'This is request from browser to proxy:\n'
                             f'{req_from_browser_str}\n'
                             '----------------------------------------------------------------------')
                req_from_browser_list = req_from_browser_str.split('\r\n')

                # check the accounting
                if client_address[0] in config_accounting_dict:
                    if int(config_accounting_dict[client_address[0]]) - len(req_from_browser_str) < 0:
                        print('Your capacity is not enough')
                        logging.info(f'{client_address} capacity is not enough')
                        raise Exception
                    else:
                        config_accounting_dict[client_address[0]] = str(int(config_accounting_dict[client_address[0]]) -
                                                                        len(req_from_browser_str))
                else:
                    print("You cannot use the proxy!")
                    logging.info(f'{client_address} cannot use the proxy!')
                    raise Exception
                req_line = req_from_browser_list[0]

                # initialize a dictionary for parsing a request
                req_header_dict = {}
                for i in range(1, len(req_from_browser_list) - 2):
                    key_name = req_from_browser_list[i].split(': ')[0]
                    value = req_from_browser_list[i].split(': ')[1]
                    req_header_dict[key_name] = value

                #fetch cache
                if cache.get(req_line) != -1:
                    print(cache.get(req_line))
                    resp_head_dict = parse_head_resp(cache.get(req_line).decode('utf-8', 'ignore').split('\r\n\r\n')[0])
                    if 'Expire' in resp_head_dict:
                        resp_date = resp_head_dict['Expire']
                        now = datetime.now()
                        stamp = mktime(now.timetuple())
                        now_date = format_date_time(stamp)
                        if now_date < resp_date:
                            client.sendall(cache.get(req_line))
                            cached_req_url = req_line.split()[1]
                            logging.info(f'\n {cached_req_url} get from cache!\n')
                            continue
                        else:
                            cached_req_url = req_line.split()[1]
                            logging.info(f'\n {cached_req_url} response expire!\n')
                            req_header_dict['If-Modified-Since'] = resp_head_dict['Last-Modified']
                            #initial request to server
                            md_req_to_server = ""
                            md_req_to_server += req_line + '\r\n'
                            for key, value in req_header_dict.items():
                                head_temp = key + ': ' + value + '\r\n'
                                md_req_to_server += head_temp
                            md_req_to_server += '\r\n\r\n'
                            sockMd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            sockMd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                            server_port = 80
                            tempHost = req_header_dict['Host']
                            server_ip = socket.gethostbyname(tempHost)
                            sockMd.connect((server_ip, server_port))
                            sockMd.sendall(md_req_to_server.encode())
                            md_resp = recv_all(sockMd)
                            md_resp_list_first_line = md_resp.decode('utf-8', 'ignore').split('\r\n')[0]
                            if md_resp_list_first_line.split()[1] == '304':
                                client.sendall(cache.get(req_line))
                                cached_req_url = req_line.split()[1]
                                logging.info(f'\n {cached_req_url} get from cache by 304!\n')
                                continue
                            elif md_resp_list_first_line.split()[1] == '200':
                                logging.info(f'\n get 200 from server!\n')
                                head_resp_to_proxy = md_resp.decode('utf-8', 'ignore').split('\r\n\r\n', 1)[0]
                                head_resp_dict = parse_head_resp(head_resp_to_proxy)
                                if 'Content-Type' in head_resp_dict and 'text/html' in head_resp_dict['Content-Type']:
                                    if config_data['HTTPInjection']['enable'] == 1:
                                        body_of_resp_to_proxy = \
                                        md_resp.decode('utf-8', 'ignore').split('\r\n\r\n', 1)[1]
                                        soup = BeautifulSoup(body_of_resp_to_proxy, 'html.parser')
                                        injection_element = soup.new_tag('p', id='ProxyInjection')
                                        injection_element.attrs[
                                            'style'] = 'background-color:blue; height:45px; width:100%; position:fixed; ' \
                                                       'top:0px; left:0px; margin:0px; padding: 15px 0 0 0;' \
                                                       'z-index: 1060; text-align: center; color: white'
                                        injection_element.insert(0, config_data['HTTPInjection']['post']['body'])
                                        if soup.body:
                                            soup.body.insert(0, injection_element)
                                            body_of_resp_to_proxy = soup.prettify()
                                        # print(body_of_resp)

                                        md_resp = (
                                                    head_resp_to_proxy + '\r\n\r\n' + body_of_resp_to_proxy).encode()
                                        client.sendall(md_resp)
                                else:
                                    client.sendall(md_resp)

                                # add to cache
                                cache.set(req_line, md_resp)
                                cached_url = req_line.split()[1]
                                logging.info(f'\n {cached_url} added to the to the cache\n')
                                sockMd.close()
                                continue
                    else:
                        client.sendall(cache.get(req_line))
                        cached_req_url = req_line.split()[1]
                        logging.info(f'\n {cached_req_url} get from cache!\n')
                        continue



                # add notify part
                if req_header_dict['Host'] in notify_dict:
                    temp = req_header_dict['Host']
                    logging.info(f'You are not able to access {temp}')
                    if notify_dict[req_header_dict['Host']] == 0:
                        raise Exception
                    else:
                        mailServer = 'smtp.gmail.com'
                        mailPort = 465
                        senderMail = 'taha.bagheri98@gmail.com'
                        receiveMail = 'taha.bagheri98@gmail.com'
                        mailMessage = req_from_browser_str
                        username = "taha.bagheri98@gmail.com"
                        password = ""
                        mail_sock = ssl.wrap_socket(socket.socket(socket.AF_INET, socket.SOCK_STREAM),
                                                    ssl_version=ssl.PROTOCOL_SSLv23)
                        mail_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        mail_sock.connect((mailServer, mailPort))
                        respon = mail_sock.recv(2048)
                        print(str(respon, 'utf-8'))
                        heloMesg = 'HELO Taha\r\n'
                        mail_sock.send(heloMesg.encode('utf-8'))
                        respon = mail_sock.recv(2048)
                        print(str(respon, 'utf-8'))
                        authMesg = 'AUTH LOGIN\r\n'
                        crlfMesg = '\r\n'
                        mail_sock.send(authMesg.encode('utf-8'))
                        respon = mail_sock.recv(2048)
                        print(str(respon, 'utf-8'))
                        user64 = base64.b64encode((username+crlfMesg).encode('utf-8'))
                        pass64 = base64.b64encode(password.encode('utf-8'))
                        mail_sock.send(user64)
                        mail_sock.send(crlfMesg.encode('utf-8'))
                        respon = mail_sock.recv(2048)
                        print(str(respon, 'utf-8'))
                        mail_sock.send(pass64)
                        mail_sock.send(crlfMesg.encode('utf-8'))
                        respon = mail_sock.recv(2048)
                        print(str(respon, 'utf-8'))
                        fromMesg = 'MAIL FROM: <' + senderMail + '>\r\n'
                        mail_sock.send(fromMesg.encode('utf-8'))
                        respon = mail_sock.recv(2048)
                        print(str(respon, 'utf-8'))
                        rcptMesg = 'RCPT TO: <' + receiveMail + '>\r\n'
                        mail_sock.send(rcptMesg.encode('utf-8'))
                        respon = mail_sock.recv(2048)
                        print(str(respon, 'utf-8'))
                        dataMesg = 'DATA\r\n'
                        mail_sock.send(dataMesg.encode('utf-8'))
                        respon = mail_sock.recv(2048)
                        print(str(respon, 'utf-8'))
                        # mailbody = mailMessage + '\r\n'
                        # mail_sock.send(mailbody.encode('utf-8'))
                        # fullStop = '\r\n.\r\n'
                        # mail_sock.send(fullStop.encode('utf-8'))
                        # respon = mail_sock.recv(2048)
                        # print(str(respon, 'utf-8'))
                        subject = 'Restricted Proxy Access'
                        body = 'We have just received a restricted http request. The Request is as below: \n' \
                               + mailMessage
                        mail_sock.send(
                            ("Subject: " + subject + "\r\n\r\n" + body + "\r\n\r\n.\r\n" + "\r\n").encode())
                        mail_sock.recv()
                        quitMesg = 'QUIT\r\n'
                        mail_sock.send(quitMesg.encode('utf-8'))
                        respon = mail_sock.recv(2048)
                        print(str(respon, 'utf-8'))
                        # Close the socket to finish
                        mail_sock.close()
                        logging.info('Mail sent to the manager')
                        raise Exception
                # add privacy part
                if config_data['privacy']['enable'] == 1:
                    req_header_dict['User-Agent'] = config_data['privacy']['userAgent']
                req_header_dict['Accept-Encoding'] = 'deflate'
                req_header_dict['Connection'] = 'Close'
                # if 'Proxy-Connection' in req_header_dict.keys():
                #     del req_header_dict['Proxy-Connection']
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
                req_to_server += '\r\n\r\n'
                # print(req_to_server)
                # print('received "%s"' % data)
                # connection.send(req_to_server.encode())
                # print('sending request to the server')
                sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_port = 80
                tempHost = req_header_dict['Host']
                server_ip = socket.gethostbyname(tempHost)
                sock2.connect((server_ip, server_port))
                logging.info(f'Proxy open a connection to the server {tempHost} {[server_ip]}')
                sock2.sendall(req_to_server.encode('utf-8', 'ignore'))
                logging.info('\n''----------------------------------------------------------------------\n'
                             'This is request from proxy to server:\n'
                             f'{req_to_server}'
                             '----------------------------------------------------------------------')
                resp_to_proxy = recv_all(sock2)
                # print(resp_to_proxy)
                head_resp_to_proxy = resp_to_proxy.decode('utf-8', 'ignore').split('\r\n\r\n', 1)[0]
                head_resp_dict = parse_head_resp(head_resp_to_proxy)

                if 'Content-Type' in head_resp_dict and 'text/html' in head_resp_dict['Content-Type']:
                    if config_data['HTTPInjection']['enable'] == 1:
                        body_of_resp_to_proxy = resp_to_proxy.decode('utf-8', 'ignore').split('\r\n\r\n', 1)[1]
                        soup = BeautifulSoup(body_of_resp_to_proxy, 'html.parser')
                        injection_element = soup.new_tag('p', id='ProxyInjection')
                        injection_element.attrs[
                            'style'] = 'background-color:blue; height:45px; width:100%; position:fixed; ' \
                                       'top:0px; left:0px; margin:0px; padding: 15px 0 0 0;' \
                                       'z-index: 1060; text-align: center; color: white'
                        injection_element.insert(0, config_data['HTTPInjection']['post']['body'])
                        if soup.body:
                            soup.body.insert(0, injection_element)
                            body_of_resp_to_proxy = soup.prettify()
                        # print(body_of_resp)

                        resp_to_proxy = (head_resp_to_proxy+'\r\n\r\n'+body_of_resp_to_proxy).encode()
                        client.sendall(resp_to_proxy)
                else:
                    client.sendall(resp_to_proxy)


                decod_resp = resp_to_proxy.decode('utf-8', 'ignore').split('\r\n\r\n')[0]
                logging.info('\n''----------------------------------------------------------------------\n'
                             'Proxy send response to client with these headers::\n'
                             f'{decod_resp}'
                             '----------------------------------------------------------------------')

                #add to cache
                if 'Cache-Control' in head_resp_dict:
                    if 'no-cache' in head_resp_dict['Cache-Control']:
                        cached_url = req_line.split()[1]
                        logging.info(f'\n {cached_url} dont added to the to the cache\n')
                else:
                    cache.set(req_line, resp_to_proxy)
                    cached_url = req_line.split()[1]
                    logging.info(f'\n {cached_url} added to the to the cache\n')

                # logging.info('\n''----------------------------------------------------------------------\n'
                #              'This is response from the server to proxy:\n'
                #              f'{header_of_resp_to_proxy}'
                #              '----------------------------------------------------------------------')
                #

                sock2.close()
                # connection.sendall(req_to_server.encode('utf-8', 'ignore'))
            except Exception as ex:
                print(ex)
                client.close()
                return False


if __name__ == "__main__":
    with open('config.json') as f:
        config_data = json.load(f)
    proxy_port = config_data['port']
    proxy_ip = "127.0.0.1"

    # initial config_accounting_dict
    config_accounting_dict = {}
    for i in range(0, len(config_data['accounting']['users'])):
        key_name = config_data['accounting']['users'][i]['IP']
        value = config_data['accounting']['users'][i]['volume']
        config_accounting_dict[key_name] = value

    # initial notify_dict
    notify_dict = {}
    if config_data['restriction']['enable'] == 1:
        for i in range(0, len(config_data['restriction']['targets'])):
            key_name = config_data['restriction']['targets'][i]['URL']
            value = config_data['restriction']['targets'][i]['notify']
            notify_dict[key_name] = value

    cache = LRUCache(config_data['caching']['size'])

    logging.basicConfig(filename='proxy.log', level=logging.INFO, format='[%(asctime)s] %(message)s',
                        datefmt='%d/%b/%Y %I:%M:%S %H:%M:%S')
    ThreadedServer(proxy_ip, proxy_port).listen()
