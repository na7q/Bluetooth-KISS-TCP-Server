import serial
import socket
import threading

# Configuration
COM_PORT = 'COM5'  # Replace with your COM port
BAUD_RATE = 9600   # Adjust the baud rate to match your device
TCP_IP = '0.0.0.0'  # Listen on all network interfaces
TCP_PORT = 8001    # Port number for the TCP server

# Function to forward data from COM port to TCP client
def com_to_tcp(serial_port, tcp_client):
    try:
        while True:
            data = serial_port.read(serial_port.in_waiting or 1)
            if data:
                print(f"COM -> TCP: {data.hex()}")  # Print data in hexadecimal for readability
                tcp_client.sendall(data)
    except (serial.SerialException, socket.error) as e:
        print(f"Error in COM to TCP: {e}")

# Function to forward data from TCP client to COM port
def tcp_to_com(serial_port, tcp_client):
    try:
        while True:
            data = tcp_client.recv(1024)
            if data:
                print(f"TCP -> COM: {data.hex()}")  # Print data in hexadecimal for readability
                serial_port.write(data)
    except (serial.SerialException, socket.error) as e:
        print(f"Error in TCP to COM: {e}")

def main():
    # Set up COM port
    try:
        serial_port = serial.Serial(COM_PORT, BAUD_RATE, timeout=1)
        print(f"Opened COM port {COM_PORT}")
    except serial.SerialException as e:
        print(f"Failed to open COM port {COM_PORT}: {e}")
        return

    # Set up TCP server
    try:
        tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_server.bind((TCP_IP, TCP_PORT))
        tcp_server.listen(1)
        print(f"Listening for TCP connections on {TCP_IP}:{TCP_PORT}")
    except socket.error as e:
        print(f"Failed to start TCP server: {e}")
        return

    try:
        tcp_client, addr = tcp_server.accept()
        print(f"TCP client connected from {addr}")

        # Create two threads for bidirectional communication
        com_to_tcp_thread = threading.Thread(target=com_to_tcp, args=(serial_port, tcp_client))
        tcp_to_com_thread = threading.Thread(target=tcp_to_com, args=(serial_port, tcp_client))

        com_to_tcp_thread.start()
        tcp_to_com_thread.start()

        # Wait for threads to finish
        com_to_tcp_thread.join()
        tcp_to_com_thread.join()

    except socket.error as e:
        print(f"Error accepting TCP connection: {e}")
    finally:
        tcp_client.close()
        serial_port.close()
        tcp_server.close()
        print("Closed connections")

if __name__ == "__main__":
    main()
