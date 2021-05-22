#!/usr/bin/env python3

import ao
import mad
import readline
import socket
import struct
import sys
import threading
from time import sleep


METHODS = ['LIST', 'PLAY', 'STOP', 'EXIT']
RECEIVE_BUFFER_SIZE = 4096
HEADER_LEN = 20


class mywrapper(object):
    def __init__(self):
        self.mf = None
        self.data = b''
        self.protocol = 'MRTSP'  # our protocol
        self.status = -1  # status code, i.e. 200, 404, etc
        self.method = ''  # methods, PLAY, STOP, etc
        self.sid = 0  # song id
        self.buf_size = 0  # buffer size used to avoid new song stutter at begining
        # clear to play (when buffered enough, or new packet arrives)
        self.ctp_flag = False
        # new song, flag if we are playing a new song that needs buffering at begining
        self.ns_flag = True

    def read(self, size):
        result = self.data[:size]
        self.data = self.data[size:]
        return result


def recv_thread_func(wrap, cond_filled, sock):
    while True:
        message_format = None
        message_array = None
        message_data = sock.recv(RECEIVE_BUFFER_SIZE + HEADER_LEN)
        if len(message_data) != 4116:  # check message length 4096 + HEADER
            # send ERRO to server
            # NOTE: uncomment for debugging
            # print(
            #     '[Recv_thread_func] Corrupted message, request re-delivery (wrong length).')
            ERRO_bytes = bytes('ERRO', encoding='utf-8')
            PROTOCOL_bytes = bytes('MRTSP', encoding='utf-8')
            send_err = struct.pack('5s4sI', PROTOCOL_bytes, ERRO_bytes, 0)
            sock.send(send_err)
            continue
        else:
            message_format = '5sI4sI' + \
                str(len(message_data) - HEADER_LEN) + 's'
            message_array = struct.unpack(message_format, message_data)
            # check message content
            if message_array[0] != b'MRTSP' or message_array[1] < 200 or message_array[1] > 500:
                # NOTE: uncomment for debugging
                # print(
                #     '[Recv_thread_func] Corrupted message, request re-delivery (wrong content).')
                ERRO_bytes = bytes('ERRO', encoding='utf-8')
                PROTOCOL_bytes = bytes('MRTSP', encoding='utf-8')
                send_err = struct.pack('5s4sI', PROTOCOL_bytes, ERRO_bytes, 0)
                sock.send(send_err)
                continue
            # send ACKN to server
            ACKN_bytes = bytes('ACKN', encoding='utf-8')
            PROTOCOL_bytes = bytes('MRTSP', encoding='utf-8')
            send_ack = struct.pack('5s4sI', PROTOCOL_bytes, ACKN_bytes, 0)
            sock.send(send_ack)

        try:
            wrap.protocol = message_array[0].decode(encoding='utf-8')
        except UnicodeDecodeError:
            pass

        wrap.status = message_array[1]
        try:
            wrap.method = message_array[2].decode(encoding='utf-8')
        except UnicodeDecodeError:
            pass
        cur_sid = message_array[3]

        if wrap.status == 404:  # an error occurs
            print('[ERROR] {0} The resource does not exist!'.format(
                wrap.status))
            sys.stdout.flush()
            continue
        elif wrap.status == 500:
            print('[ERROR] {0} Server error!'.format(wrap.status))
            sys.stdout.flush()
            continue

        if wrap.method == 'LIST':
            sys.stderr.write(message_array[4].decode(encoding='utf-8'))
            sys.stdout.flush()
        elif wrap.method == 'PLAY':
            cond_filled.acquire()
            if wrap.sid != cur_sid:  # switch a song to play
                wrap.data = b''
                wrap.sid = cur_sid
                wrap.buf_size = 0
                wrap.ctp_flag = False
                wrap.ns_flag = True
            wrap.data += message_array[4]
            if wrap.ns_flag == True:  # buffering to avoid stutter
                wrap.buf_size += 1
                if wrap.buf_size >= 32:
                    print('[Recv_thread_func] Buffered {0} packets to avoid stutter!'.format(
                        wrap.buf_size))
                    wrap.ctp_flag = True
                    wrap.ns_flag = False
                    wrap.buf_size = 0
                    cond_filled.notify()
            elif wrap.ctp_flag == False:  # when a new packet arrives
                wrap.ctp_flag = True
                cond_filled.notify()
            cond_filled.release()
        elif wrap.method == 'STOP':
            cond_filled.acquire()
            wrap.buf_size = 0
            wrap.ns_flag = True
            wrap.ctp_flag = False
            wrap.data = b''
            cond_filled.release()
        elif wrap.method == 'EXIT':
            break


def play_thread_func(wrap, cond_filled, dev):
    while True:
        cond_filled.acquire()
        while True:
            if wrap.ctp_flag == True:
                break
            cond_filled.wait()  # just wait to play, either buffer enough, or new packet
        wrap.ctp_flag = False
        cond_filled.release()
        wrap.mf = mad.MadFile(wrap)
        while True:
            buf = wrap.mf.read()
            if wrap.method == 'STOP':
                break
            if buf is None:
                break
            dev.play(bytes(buf), len(buf))


def main():
    if len(sys.argv) < 3:
        print('Usage: %s <server name/ip> <server port>' % sys.argv[0])
        sys.exit(1)

    wrap = mywrapper()
    cond_filled = threading.Condition()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((sys.argv[1], int(sys.argv[2])))

    recv_thread = threading.Thread(
        target=recv_thread_func,
        args=(wrap, cond_filled, sock)
    )
    recv_thread.daemon = True
    recv_thread.start()

    dev = ao.AudioDevice('pulse')
    play_thread = threading.Thread(
        target=play_thread_func,
        args=(wrap, cond_filled, dev)
    )
    play_thread.daemon = True
    play_thread.start()

    PROTOCOL_bytes = bytes('MRTSP', encoding='utf-8')

    while True:
        line = input('>> ')
        one_arg = False
        if ' ' in line:
            cmd, args = line.split(' ', 1)
        else:
            cmd = line
            one_arg = True

        if cmd in ['l', 'list']:
            print('The user asked for list.')
            LIST_bytes = bytes(METHODS[0], encoding='utf-8')
            send_data = struct.pack('5s4sI', PROTOCOL_bytes, LIST_bytes, 0)
            sock.send(send_data)
        if cmd in ['p', 'play']:
            if one_arg == False:  # input does have sid
                print('The user asked to play:', args)
                sid = int(args)
                PLAY_bytes = bytes(METHODS[1], encoding='utf-8')
                send_data = struct.pack(
                    '5s4sI', PROTOCOL_bytes, PLAY_bytes, sid)
                sock.send(send_data)
        if cmd in ['s', 'stop']:
            print('The user asked for stop.')
            STOP_bytes = bytes(METHODS[2], encoding='utf-8')
            send_data = struct.pack('5s4sI', PROTOCOL_bytes, STOP_bytes, 0)
            sock.send(send_data)
        if cmd in ['quit', 'q', 'exit']:
            if wrap.method == 'PLAY':
                # NOTE: don't worry, the server will not keep sending after
                # the song ended! check server.py:203
                print('Please stop your song before leaving!')
                continue
            sys.exit(0)

    sock.close()


if __name__ == '__main__':
    main()
