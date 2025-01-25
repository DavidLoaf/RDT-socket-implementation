import socket
import struct
import threading
import time
import random

# RUN THIS SECOND
# This is where the heavy lifting is done

class ReliableSender:

    def __init__(self, host, port):
        self.server_address = (host, port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(0.65)  # Timeout for retransmission
        self.window_size = 1  # Sliding window size
        self.congestion_window = 1
        self.congestion_threshold = 8
        self.sliding_window_base = 0
        self.next_seq_number = 0
        self.to_send_data_buffer = [] 
        self.lock = threading.Lock()
        self.acknowledged = {}
        self.running = True  # Flag to control the listening thread (stops errors from using recvfrom on a closed socket)

    def create_packet(self, seq_num, data):
        header = struct.pack('!I', seq_num) #'!I' makes seq_num a binary unsigned int for transmissionn
        return header + data.encode()

    def send_packet(self, seq_num, data):
        
        # We want to simulate errors. We will make it so that each packet has a small chance of not sending
        # Let's give it a 5% send failure rate. In other words, we wont bother with sending a packet give
        # a failure occurs:

        if random.random() > 0.05:
            # Create packet
            packet = self.create_packet(seq_num, data)

            #send packet
            self.socket.sendto(packet, self.server_address)
            print(f"Sent packet with sequence number {seq_num}")

        else:
            print(f"SIMULATED LOSS: PACKET {seq_num}")
        
    # Split data into chunks and send using sliding window
    def send_data(self, data):

        # Load data into buffer, from index 0 to len(data), in steps of the window size.
        for i in range(0, len(data), self.window_size):

            # get data from index i to i + window_size
            chunk = data[i:i + self.window_size]
            
            # add the sliced chunk to the buffer array
            self.to_send_data_buffer.append(chunk)

        # Start connection establishment (SYN)
        self.establish_connection()

        # Start listening for ACKs in a separate thread
        threading.Thread(target=self.listen_for_acks).start()

        # Start sending data
        while self.sliding_window_base < len(self.to_send_data_buffer):

            self.lock.acquire()
            while self.next_seq_number < self.sliding_window_base + self.congestion_window and self.next_seq_number < len(self.to_send_data_buffer):

                self.send_packet(self.next_seq_number, self.to_send_data_buffer[self.next_seq_number])
                self.acknowledged[self.next_seq_number] = False
                self.next_seq_number += 1

            self.lock.release()
            time.sleep(0.2)  # Allow time for ACKs and retransmissions

        # Check for unacknowledged packets and handle timeout
        self.lock.acquire()
        for seq_num in range(self.sliding_window_base, self.next_seq_number):

            if not self.acknowledged[seq_num]:

                self.handle_timeout()
                break

        self.lock.release()

        # Terminate the connection (FIN)
        self.terminate_connection()

    def listen_for_acks(self):
        
        old_ack = 0
        while self.running:
            
            try:
                data, unused = self.socket.recvfrom(1024)
                
                # if its not running then why would we do this. We get an error if we dont unpack a NUMBER.
                ack_num = None
                if(self.running):
                    ack_num = struct.unpack('!I', data)[0]  # Extract ACK number

                else:
                    return # straight up return this whole function cause we're not running anymore.
                old_ack = ack_num
                print(f"Received ACK for sequence number {ack_num}")

                self.lock.acquire()
                if ack_num in self.acknowledged:

                    self.acknowledged[ack_num] = True

                    # Advance the base if the current sequence is acknowledged
                    if ack_num == self.sliding_window_base:

                        while self.sliding_window_base in self.acknowledged and self.acknowledged[self.sliding_window_base]:

                            self.sliding_window_base += 1
                            # Adjust congestion control
                            if self.congestion_window < self.congestion_threshold:
                                self.congestion_window *= 2  # Slow start phase
                            else:
                                self.congestion_window += 1  # Congestion avoidance phase
                self.lock.release()

            # Fought with this for a while, fixes recvfrom() on a closed socket when closing the connection
            except socket.timeout:
                print('Timeout! Reverting seq_num to last pack ACK.')
                self.handle_timeout()
            except OSError as e:
                if self.running:
                    print(f"OSError occurred: {e}")
                break

        print("Listener thread stopped.")


    # Handles timeout and resends the packet
    def handle_timeout(self):

        print("Timeout occurred. Retransmitting...")
        self.lock.acquire()

        # Reduce the congestion window size to avoid further timeouts
        self.congestion_threshold = max(self.congestion_window // 2, 1)
        self.congestion_window = 1

        # send the packed that was unacked, and send the packets after that pack as well like in Go Back N.
        for i in range(self.sliding_window_base, self.next_seq_number):

            if not self.acknowledged[i]:
                self.send_packet(i, self.to_send_data_buffer[i])

        self.lock.release()

    # Three-way handshake
    def establish_connection(self):

        print("Sending SYN packet with sequence number 0: ")
        self.send_packet(0, "SYN")
        
        while True:
            
            try:
                data, unused = self.socket.recvfrom(1024)
                if data.decode() == "SYN-ACK":
                    print("Connection established, sending final ACK with sequence number 0:")

                    self.send_packet(0, "ACK")
                    break

            except socket.timeout:
                print("Retransmitting SYN...")
                self.send_packet(0, "SYN")

    # Start connection termination by sending FIN and waiting for FIN-ACK
    def terminate_connection(self):

        print("Connection terminated, sending FIN with sequence number 0...")
        self.running = False
        self.send_packet(0, "FIN")
        
        while True:
            
            try:

                data, unused = self.socket.recvfrom(1024)
                if data.decode() == "FIN-ACK":
                    
                    print("Received FIN-ACK, connection closed.")
                    self.running = False  # Wretched beast to get rid of recvfrom() on the closed socket in listen_for_acks
                    self.socket.close()
                    break

            except socket.timeout:
                print("Timeout occurred. Retransmitting FIN...")
                self.send_packet(0, "FIN")

        print("Socket closed.")

# Starting sender
sender = ReliableSender(host="127.0.0.1", port=12345)
# This can be changed to gibberish if we need more data to send
message = "Did you know? Octopuses have three hearts and blue blood. No matter how smart they are, that's pretty freaky!"
print("Sender started. Sending data...")
sender.send_data(message)



