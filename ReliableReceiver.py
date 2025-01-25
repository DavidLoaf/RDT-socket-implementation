import socket
import struct
import threading
import random

# RUN THIS FIRST
# Simple receiver to unpack data packets sent by ReliableSender class and send ACKs

class ReliableReceiver:

    # Start a listening socket on the local host with UDP
    def __init__(self, port):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("0.0.0.0", port))
        self.expected_seq_number = 0

    # Listen using recvfrom() for packets on the port
    def listen(self):

        old_sequence_num = 0
        while True:
            
            # I don't really know how much to recvfrom so increase by *2 if it's causing problems
            data, addr = self.socket.recvfrom(1024)

            # Get the information ignoring the sequence number
            packet_payload = data[4:].decode()  

            # Handle control the handshake + closing the connection
            if packet_payload == "SYN":
                print("Received SYN, sending SYN-ACK")
                self.socket.sendto("SYN-ACK".encode(), addr)

            elif packet_payload == "ACK":
                print("Received ACK, connection established")

            elif packet_payload == "FIN":
                print("Received FIN, sending FIN-ACK")
                self.socket.sendto("FIN-ACK".encode(), addr)

                #time to send the next message, eh?
                old_sequence_num = 0 
                self.expected_seq_number = 0
                
            else:
                
                # Handle data packets https://docs.python.org/3/library/struct.html#struct.Struct.unpack
                seq_num = struct.unpack('!I', data[:4])[0]
                if seq_num == self.expected_seq_number:
                    print(f"Received packet with sequence number {seq_num}: {packet_payload}")
        
                    self.expected_seq_number += 1
                    old_sequence_num = seq_num

                    self.send_ack(seq_num, addr)
                else:
                    self.send_ack(old_sequence_num, addr)

    # Send acknowledgment for the sequence number
    def send_ack(self, seq_num, addr):

        ack_packet = struct.pack('!I', seq_num) # create unsigned binary integer suitable for transmission
        self.socket.sendto(ack_packet, addr)
        print(f"Sent ACK for sequence number {seq_num}")



# Starts the receiver
receiver = ReliableReceiver(port=12345)
print("Receiver started. Listening for packets...")
receiver.listen()