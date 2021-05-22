#!/usr/bin/env python3

import os
import socket
import struct
import sys
from threading import Lock, Thread

import time
import copy


QUEUE_LENGTH = 10
RECV_BUFFER = 16
SEND_BUFFER = 4096
METHODS = ["LIST", "PLAY", "STOP", "EXIT"]


class Client:
    def __init__(self):
        self.lock = Lock()
        self.protocol = "MRTSP"
        self.method = ""
        self.sid = 0
        self.updated = False
        self.list_flag = False
        self.err_flag = False
        self.ack_flag = False
        self.det_flag = False


def servsend(client, csock, serial_format, protocol, statcode, method, sid, payload):
    # This is the server partial send function. It sends to clients and
    # log bytes sent. If we finished sending all frames, or the connected
    # socket closed, it will break and return 0. Otherwise, i.e. client
    # requests a change (switch played song, or stop), we will return the
    # bytes actually sent. So the client_write will know if it's finished
    # or needs to check client object fields to send new data.
    bytes_sent = 0
    if len(payload) <= SEND_BUFFER:
        # send in one frame, basically only used by list
        message = struct.pack(
            serial_format, protocol, statcode, method, sid, payload)
        try:
            bytes_sent += csock.send(message)
            while True:
                if client.det_flag != True:
                    continue
                elif client.det_flag == True and client.err_flag == True:
                    client.lock.acquire()
                    csock.send(message)
                    client.det_flag = False
                    client.err_flag = False
                    client.lock.release()
                elif client.det_flag == True and client.ack_flag == True:
                    client.lock.acquire()
                    client.det_flag = False
                    client.ack_flag = False
                    client.lock.release()
                    break
        except IOError:
            return 0
    else:
        payload_size = len(payload)
        bytes_left = payload_size

        # partial send
        # seqnum = 1  # this is used for debug
        while bytes_left > 0:
            if bytes_left < SEND_BUFFER:
                payload_chunk = payload
                print("[Servsend] Send last chunk!")
            else:
                payload_chunk = payload[: SEND_BUFFER]
            message = struct.pack(
                serial_format, protocol, statcode, method, sid, payload_chunk)
            if (len(message)) != 4116:
                print("[Servsend] Packing corrupted!")
            try:
                bytes_sent += csock.send(message)
                while True:
                    if client.det_flag != True:
                        continue
                    elif client.det_flag == True and client.err_flag == True:
                        # NOTE: uncomment for debugging
                        # print(
                        #     "[Servsend] Package corrupted due to internet state, resending...")
                        client.lock.acquire()
                        csock.send(message)
                        client.det_flag = False
                        client.err_flag = False
                        client.lock.release()
                    elif client.det_flag == True and client.ack_flag == True:
                        client.lock.acquire()
                        # NOTE: uncomment for debugging!
                        # print("[Servsend] Seqnum {0} acknowleged!".format(seqnum))
                        # seqnum += 1  # this is used for debugging
                        client.det_flag = False
                        client.ack_flag = False
                        client.lock.release()
                        break
            except IOError:
                return 0
            payload = payload[SEND_BUFFER:]
            bytes_left = len(payload)

            # check for method updates
            if client.method != "PLAY" or sid != client.sid:
                return bytes_sent
        print("[Client_write] Left partial send loop!")

    return 0


def list_write(client, csock, cport, songs):
    # This is an additional thread used for send list response, as we are
    # not allowed to stop, during playing when asked for a list. I fail
    # to see if there's another way to do this. Using client.list_flag.
    print("[List_write] Started!")
    while True:
        if client.method == "EXIT":
            break

        # just keep checking if we need a list
        if client.list_flag == True:
            print("[List_write] Got a list request!")
            lpayload = ""
            for key in songs:
                lpayload += str(key) + ": " + \
                    songs[key]["name"] + "\n"
            lpayload = bytes(lpayload, encoding="utf-8")
            serial_format = "5sI4sI" + str(SEND_BUFFER) + "s"
            protocol = bytes(client.protocol, encoding="utf-8")
            sid = copy.deepcopy(client.sid)
            servsend(client, csock, serial_format, protocol, 200, bytes(
                "LIST", encoding="utf-8"), sid, lpayload)
            client.lock.acquire()
            client.list_flag = False
            client.lock.release()

    print("[List_write] Stopped!")


def client_write(client, csock, cport, musicdir, songs):
    # This is the client_write, that will send data frames to client. It
    # will keep checking if we have request from client and send messages
    # accordingly.
    print("[Client_write] Started!")
    while True:
        try:
            # break if user wants to exit
            if client.method == "EXIT":
                break

            # we only do things when there's an update for client fields
            # and the lock is available, to avoid accessing the lock too
            # frequently.
            if client.updated and not client.lock.locked():
                print("[Client_write] I acquired for metadata!")
                if client.method != "":
                    print("[Client_write] Method:", client.method)
                if client.method in METHODS:
                    statcode = 0
                    payload = ""
                    client.lock.acquire()

                    # when the user wants to play
                    if client.method == "PLAY":
                        # check if song exist
                        if client.sid < 1 or client.sid > len(songs):
                            statcode = 404
                            payload = "[SERVER] Request song does not exist!"
                            payload = bytes(payload, encoding="utf-8")
                        else:
                            print("[Client_write] Client requests sid " +
                                  str(client.sid) + "!")
                            statcode = 200
                            song = songs[client.sid]["name"]
                            payload = open(musicdir + "/" + song, "rb").read()

                    # if the user wants to stop playing
                    elif client.method == "STOP":
                        print("[Client_write] Client requests to stop!")
                        statcode = 200
                        payload = "[SERVER] Stop request acknowleged!"
                        payload = bytes(payload, encoding="utf-8")

                    # prepare frame headers
                    serial_format = "5sI4sI" + str(SEND_BUFFER) + "s"
                    protocol = bytes(client.protocol, encoding="utf-8")
                    method = bytes(client.method, encoding="utf-8")
                    sid = copy.deepcopy(client.sid)
                    client.lock.release()
                    print("[Client_write] I released for metadata!")

                # send and determine status by sending result
                send_result = servsend(
                    client, csock, serial_format, protocol, statcode, method, sid, payload)
                if send_result == 0:  # send finished, or cannot send at all
                    client.lock.acquire()
                    print("[Client_write] Server send stopped!")
                    client.method = ""  # stop and wait for new request
                    client.sid = 0
                    client.updated = False  # NOTE: nothing is send without a new request since now!
                    client.lock.release()
                    print("[Client_write] Set client status to none")
                else:  # just continue to see new request
                    print(
                        "[Client_write] Client requested something else before last send completed!")
                    continue
        except KeyboardInterrupt:
            break
        except Exception as err:
            print("[Client_write] Unexpected server error!")
            print("[Client_write] Error:", str(err))
            servsend(client, csock, b"5sI4sI4096s", b"MRTSP",
                     500, b"", 0, b"[SERVER] Internal server error!")
    print("[Client_write] Stopped!")


def client_read(client, csock, cport):
    # This is the client_read, it just keep reading requests from the user.
    print("[Client_read] Listening port " + str(cport) + "!")
    while True:
        try:
            message = csock.recv(RECV_BUFFER)
            if len(message) > 0:
                message = struct.unpack("5s4sI", message)
                protocol = message[0].decode(encoding="utf-8")
                method = message[1].decode(encoding="utf-8")
                if not client.lock.locked():
                    client.lock.acquire()
                    if method == "ACKN":
                        client.protocol = protocol
                        client.det_flag = True
                        client.ack_flag = True
                        client.err_flag = False
                    elif method == "ERRO":
                        client.protocol = protocol
                        client.det_flag = True
                        client.ack_flag = False
                        client.err_flag = True
                    elif method == "LIST":
                        client.protocol = protocol  # we don't need to change client.updated
                        client.list_flag = True  # we have a special field for this case
                    else:
                        client.protocol = protocol
                        client.method = method
                        client.sid = message[2]
                        client.updated = True
                    client.lock.release()
            else:
                print("[Client_read] Recieve zero bytes, disconnected!")
                client.lock.acquire()
                client.protocol = ""
                client.method = "EXIT"  # just trying to be clean when exiting
                client.sid = 0
                client.updated = False
                client.list_flag = False
                client.lock.release()
                break
        except KeyboardInterrupt:
            break
        except socket.error:  # this is used for non-blocking socket when debugging
            continue
        except Exception as e:
            print("[Client_read] Unexpected exceptions!")
            print(len(message))
            print(message)
            print(str(e))
    print("[Client_read] Stopped!")


def get_mp3s(musicdir):
    # Get a list of mp3 and return it for future useage.
    print("[STATUS] Reading music files...")
    songs = {}
    sid = 1
    for filename in os.listdir(musicdir):
        if not filename.endswith(".mp3"):
            continue
        else:
            value = {"name": filename}
            songs[sid] = value
            sid += 1
    print("[STATUS] Found {0} song(s)!".format(len(songs)))
    return songs


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: python server.py [port] [musicdir]")
    if not os.path.isdir(sys.argv[2]):
        sys.exit("Directory '{0}' does not exist".format(sys.argv[2]))

    # initialize
    port = int(sys.argv[1])
    songs = get_mp3s(sys.argv[2])
    threads = []

    # create a socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port))  # changes this for localhost / AWS EC2
    s.listen(QUEUE_LENGTH)

    while True:
        try:
            # listening for connection and start threads
            conn, addr = s.accept()
            client = Client()
            t1 = Thread(target=client_read, args=(client, conn, addr[1]))
            threads.append(t1)
            t2 = Thread(target=client_write, args=(
                client, conn, addr[1], sys.argv[2], songs))
            threads.append(t2)
            t3 = Thread(target=list_write, args=(client, conn, addr[1], songs))
            threads.append(t3)
            t1.start()
            t2.start()
            t3.start()
        except socket.error:
            continue
        except KeyboardInterrupt:
            print("[EXCEPTION] Interrupted by keyboard!")
            break

    s.close()
    print("[STATUS] Server Stopped!")


if __name__ == "__main__":
    main()
