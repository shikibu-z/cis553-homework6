# CIS 553 Homework 6 Music Streaming Sercive

Group 36:
+   Junyong Zhao: junyong@seas.upenn.edu
+   Qianfan Guo: guoqia@seas.upenn.edu

## Setup Instructions

**It took a long time for the professor and us to work a way around the play-setup
issue. And we have tested thoroughly our client on the host Linux machine outside
VM and our server on AWS EC2! Please contact the professor and us before you deduct
points for cannot get the code to run!**

+   This project is based on **Python 3**, for both the client and the server.

+   The reason that we are using Python 3, **by professor's instruction**,
    instead of the default Python 2 setup in the VM is because of the compatibility
    issue of playing music from VM throught the `ao` library on both group members'
    computer. We just couldn't get the play working throught the VM!

+   We developed our client directly on Junyong's host machine running Ubuntu 20.04
    LTS. The server is generally not affected by the playing issue. However, we made 
    the server Python 3 still, for `open('rb')`, `read()` and `struct.pack/unpack`
    difference on `str` and `bytes(encoding)` object in Python 2 and Python 3.

+   To setup and run our code, if you are also using a Linux machine instead of a VM,
    please ensure that the following packages are installed at your Python 3
    environment correctly.

    ```
    libmad0-dev
    python3-pyao
    ao (should be installed at ~/.local/python3.x/site-packages/ao-0.0.1.dist-info)
    python-dev
    pymad (compile and build from GitHub)
    ```

+   You could try running the following command to install.

    ```
    sudo apt install libmad0-dev
    sudo apt install python3-pyao
    pip3 install ao
    sudo apt install python-dev
    git clone https://github.com/jaqx0r/pymad.git
    cd pymad
    git checkout "144daa3afa7935af2e6d68a5e8a67eaf77a7c91c"
    sudo python3 setup.py build
    sudo python3 setup.py install
    ```

+   We don't know what is needed for running our client through your VM (if you are
    using one). But please make sure that the provided `mp3-example.py` works with
    Python 3 before runnning our project! If
    ```
    python3 mp3-example.py music/cinematrik\ -\ Revolve.mp3
    ```
    plays fine, then you are probably okay. More
    specifically, to listen the music, you will have to change

    ```
    [line 35] f = open(sys.argv[1], 'r') -> f = open(sys.argv[1], 'rb')
    [line 51] dev.play(buffer(buf), len(buf)) -> dev.play(bytes(buf), len(buf))
    ```

    Making the music data read in and played `bytes` object is the key point. We
    believe it would be more efficient to just contact the professor if you encounter
    any problem!

+   To run the server, type `python3 server.py 55353 music`

+   To run the client, type `python3 client.py [EC2 IP] 55353`

## Running and Testing

+   After you get it to run, feel free to use the line commented as `"NOTE:"` to print
    out useful information. We have choose to minimize those messages for a better 
    experience.

+   The experiences to test the client and the server locally instead of AWS will be 
    generally better due to unstable internet connection.

+   The print out messages is **especially useful** when you find the music is 
    stuttering. We have tried our best to buffer for a smooth play, but depending on 
    your internet connection with the AWS server, the packet corruption rate will 
    vary. You could choose to uncomment the `"NOTE:"` field and see about 
    re-transmissions due to network.
