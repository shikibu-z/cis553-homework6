%%%
title = "CIS 553 Homework6: Music Streaming Protocol"
abbrev = "HW6"
obsoletes = [6536]
ipr= "trust200902"
area = "Internet"
workgroup = "Network Working Group"
submissiontype = "IETF"
keyword = [""]
date = 2021-04-21T00:00:00Z

[seriesInfo]
name = "RFC"
value = "8341"
stream = "IETF"
status = "standard"

[[author]]
initials="J.Z."
surname="Zhao"
fullname="Junyong Zhao"
abbrev = "Group 36"
organization = "Group 36"
  [author.address]
  email = "junyong@seas.upenn.edu"
[[author]]
initials="Q.G."
surname="Guo"
fullname="Qianfan Guo"
abbrev = "Group 36"
organization = "Group 36"
  [author.address]
  email = "guoqia@seas.upenn.edu"
%%%

{mainmatter}

## Introduction

The My Real Time Streaming Protocol, or MRTSP, is an application-level protocol for control over the delivery of data with real-time properties. MRTSP enables controlled demand of real time audio(.mp3) data. It supports multiple data delivery sessions. MRTSP uses RTSP as a main reference.

My Real Time Streaming Protocol (MRTSP) establishes and supports a single or several time-synchronized streams of continuous audio data. It is built directly on top of raw sockets. The server is able to handle multiple server requests simultaneously.

## MRTSP Message

The messages are text based, like RTSP[@RFC2326]. The package message is serialized through the Python 3 struct library with UTF-8 encoding.

When a client send request to the server, the message is purely text based. It has a length of 16 bytes, specifying protocol, method and song id.

When a server send response to the client, the message includes binary data as well. It has a length of 4116 with 20 header and 4096 message length, which will include media file or server response messages encoded in UTF-8.

Please see the following section for detailed explanation.

## General Message Fields

### Client Request Header (Message)

The client requests header is 16 bytes long, with 5 bytes identifying the protocol, 4 bytes used for method, and 4 bytes used for song id, if there is any, 0 otherwise. The length that is actually packed is longer than the message itself, since the Python struct pack will fill '\x00' behind some text to achieve a better memory alignment (as multiples of 4). This header will actually be a full message of request as it contains all we needed for a request packet.

The request header (message) generally looks like

{#fig1}
~~~
[PROTOCOL] [METHOD] [SID]
~~~

### Server Response Message

The server will response messages of 4116 bytes, with 20 bytes for header. The header includes 5 bytes for protocol, 4 bytes for status code, 4 bytes for method and 4 bytes for song id, if there is any, 0 otherwise. The size 20 bytes is a bit larger than the actually data for the same reason as client requests.

The response message generally looks like

{#fig2}
~~~
[PROTOCOL] [STATUS CODE] [METHOD] [SID] [PAYLOAD]
~~~

The payload field here is the content responded. It could be either a text message or a binary data of music chunk. The payload has a fixed size of 4096, and it is binary originated from text with UFT-8 encoding, or a slice of binary mp3 data imported by Python's library read function.

## Method Definition

The request and response will use the same protocol name and method text, as listed below. The protocol will always be text messages of "MRTSP".

{#fig3}
~~~
1. LIST: Request/response a message that deal with listing playable songs.

2. PLAY: Request/response a message that deal with playing a song.

3. STOP: Request/response a message that deal with stop a playing song.

4. EXIT: Request/response a message that deal with client ask to terminate session.
~~~

During data transmission specifically when a song is being played, this method field is also used as a token for message acknowledgement or re-transmission request. As we will definitely encounter message corruption when the internet state is not steady enough.

{#fig4}
~~~
1. ACKN: Means the message passed sanity check, clear to send next one.

2. ERRO: Means corruption detected, either in length or content. 
   Need to resend the packet again.
~~~

By doing sanity check for each packet through length and content field, we will be able to differentiate the beginning and ending of each packet without being messed with multiple messages arrive at the same time.

## Status Code Definition

Each response will contain a status code indicating the how the previous request is being handled. The status code used here inherit the internet convention, as listed below.

{#fig5}
~~~
1. 200: Indicating the request is handled successfully.

2. 404: Indicating the request asked something that cannot be found.

3. 500: Indicating some error that is not caused by this request occurred.
~~~

## Some Examples for Communicating

Here, we are providing some examples to run through MRTSP:

{#fig6}
~~~
1. PLAY: sid 2, payload music chunk of 4096
 
C->S: [MRTSP] [PLAY] [2]

S->C: [MRTSP] [200] [PLAY] [2] [PAYLOAD[0]]

C->S: [MRTSP] [ACKN] [2]

S->C: [MRTSP] [200] [PLAY] [2] [PAYLOAD[1]]

C->S: [MRTSP] [ERRO] [2]

S->C: [MRTSP] [200] [PLAY] [2] [PAYLOAD[1]]

Continue
...

2. STOP: sid 2

C->S: [MRTSP] [STOP] [2]

S->C: [MRTSP] [200] [STOP] [2] [MESSAGE]

MESSAGE: {b"[SERVER] Stop acknowledged!"}

3. LIST:

C->S: [MRTSP] [LIST] [0]

S->C: [MRTSP] [200] [LIST] [MESSAGE]

MESSAGE: {List string packed}
~~~

## Server-Client Interaction

The server will several flags for each client, to determine the state of a client and response to requests accordingly, as listed below.

{#fig7}
~~~
1. sid: The song id played to the client. Default is 0.

2. updated: If the client changed the method field.

3. list_flag: If the client ask for a list, to assure listing while playing.

4. err_flag: If the client says the packet is corrupted.

5. ack_flag: If the client acknowledge the packet.

6. det_flag: If there is a response from client concerning the sent packet.
   This is used together with err_flag and ack_flag, for re-transmission.

7. method: The client's request to PLAY, or STOP, etc.
~~~

The client also uses several flags, to better play and receive. As listed below.

{#fig8}
~~~
1. status: Used for status code, 200, 404, etc.

2. method: Used for method like PLAY, STOP, etc.

3. sid: The song id, as always.

4. buf_size: A buffer size when playing from the beginning, to avoid stutter.

5. ctp_flag: Clear-to-play flag, indicating the client have enough data to play.
   This is used to avoid stutter as much as possible.

6. ns_flag: New-song flag, use to determine if we are playing a new song.
~~~

### Client-Server Status Transition

Here are expected behaviors for client-server interaction and status change.

For the server, it will keep listening client requests and response accordingly. The server will change its state when the client requests with a new method, or a new sid. If the client requests to play another song, or stop, it will jump out of the sending function and re-construct everything it needed to either stop sending, or stream the newly requested song. If the client requests a list, it will use another thread to send the list without blocking music data streaming.

For the client, it will send request and change status based on server's responded status code and method, unless otherwise specified by the user (exit). If a song is going to be played, the client is going to buffer for 32 packets before starting to avoid stuttering. When the client is continuously receiving from the server, it will store at least one packet (something new) before notifying the play thread to actually play, thereby, avoiding play thread to spin-wait and consume data too fast. These are all designed to avoid stuttering.

These behaviors are all achieved through condition object and stored flags at server and client. When the internet connection is steady, the application should be responsive and seamless. Please refer to the code and submitted readme for details about implementation.

{backmatter}

<reference anchor='RFC2326' target=''>
 <front>
 <title>Real Time Streaming Protocol (RTSP)</title>
  <author initials='H.S.' surname='Schulzrinne' fullname='H. Schulzrinne'></author>
  <author initials='A.R.' surname='Rao' fullname='A. Rao'></author>
  <author initials='R.L.' surname='Lanphier' fullname='R. Lanphier'></author>
  <date year='1998' />
 </front>
 </reference>
