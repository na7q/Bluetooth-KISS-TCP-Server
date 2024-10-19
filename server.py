import socket
import threading
import asyncio
from bleak import BleakScanner
import os
import signal
from threading import Event

# Bluetooth connection settings
DEVICE_NAMES = ["UV-PRO", "VR-N76", "GA-5WB"] # List with possible device names
DATA_CHANNEL_ID = 3      # Replace with your device's RFCOMM channel

# TCP Server settings
TCP_HOST = '0.0.0.0'  # Listen on all interfaces
TCP_PORT = 8001       # TCP port number

# Create a global shutdown event
shutdown_event = Event()

async def find_bluetooth_device(device_name):
    """Scan for Bluetooth devices and return the MAC address of the specified device."""
    print("Scanning for Bluetooth devices...")
    devices = await BleakScanner.discover()

    for device in devices:
        print(f"Found Bluetooth device: {device.name} - {device.address}")
        if device.name == device_name:
            return device.address

    print(f"Device '{device_name}' not found.")
    return None


def connect_bluetooth(mac_address, channel):
    """Establish Bluetooth socket connection using RFCOMM protocol."""
    try:
        # Set up Bluetooth RFCOMM socket
        bt_sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        bt_sock.connect((mac_address, channel))
        print(f"Connected to {mac_address} on channel {channel}")
        return bt_sock
    except Exception as e:
        print(f"Failed to connect to {mac_address}: {e}")
        return None

def start_tcp_server(bt_sock, tcp_sock):
    """Start a TCP server that forwards data between TCP clients and Bluetooth socket."""
    try:
        tcp_sock.settimeout(1.0)  # Set a timeout to allow periodic checks for shutdown_event
        tcp_sock.bind((TCP_HOST, TCP_PORT))
        tcp_sock.listen(1)
        print(f"TCP server started on port {TCP_PORT}. Waiting for client connection...")

        while not shutdown_event.is_set():
            try:
                client_sock, client_address = tcp_sock.accept()  # Accept TCP client connection
                print(f"Client connected from {client_address}")

                # Create separate daemon threads to handle Bluetooth <-> TCP data transfer
                bt_to_tcp_thread = threading.Thread(target=handle_bt_to_tcp, args=(bt_sock, client_sock), daemon=True)
                tcp_to_bt_thread = threading.Thread(target=handle_tcp_to_bt, args=(client_sock, bt_sock), daemon=True)

                bt_to_tcp_thread.start()
                tcp_to_bt_thread.start()
            except socket.timeout:
                continue  # Timeout occurred, loop again to check for shutdown_event

    except Exception as e:
        print(f"TCP Server error: {e}")



def handle_bt_to_tcp(bt_sock, client_sock):
    """Forward data from Bluetooth to the TCP client."""
    try:
        bt_sock.settimeout(1.0)  # Set a timeout to allow periodic checks for shutdown_event
        while not shutdown_event.is_set():
            try:
                data = bt_sock.recv(1024)  # Receive data from Bluetooth device
                if data:
                    print(f"Received from Bluetooth: {data}")
                    client_sock.sendall(data)  # Send the data to the TCP client
            except socket.timeout:
                continue  # Timeout occurred, loop again to check for shutdown_event
    except Exception as e:
        print(f"Error forwarding Bluetooth to TCP: {e}")
    finally:
        client_sock.close()

def handle_tcp_to_bt(client_sock, bt_sock):
    """Forward data from the TCP client to the Bluetooth device."""
    try:
        client_sock.settimeout(1.0)  # Set a timeout to allow periodic checks for shutdown_event
        while not shutdown_event.is_set():
            try:
                data = client_sock.recv(1024)  # Receive data from TCP client
                if data:
                    print(f"Received from TCP client: {data}")
                    bt_sock.sendall(data)  # Send the data to the Bluetooth device
            except socket.timeout:
                continue  # Timeout occurred, loop again to check for shutdown_event
    except Exception as e:
        print(f"Error forwarding TCP to Bluetooth: {e}")
    finally:
        client_sock.close()



def graceful_shutdown(bt_sock, tcp_sock=None):
    print("Shutting down gracefully...")
    shutdown_event.set()  # Signal all threads to stop
    if bt_sock:
        bt_sock.close()
        print("Bluetooth socket closed.")
    if tcp_sock:
        tcp_sock.close()
        print("TCP server socket closed.")
    os._exit(0)  # Forcefully exit the program (in case threads are stuck)



def main():
    mac_address = None

    # Attempt to find a Bluetooth device from the list of names
    for device_name in DEVICE_NAMES:
        print(f"Attempting to find Bluetooth device: {device_name}")
        mac_address = asyncio.run(find_bluetooth_device(device_name))

        if mac_address:
            print(f"Found Bluetooth device: {device_name}")
            break
    else:
        print("Failed to find any Bluetooth device. Exiting...")
        return

    # Connect to the Bluetooth device using the found MAC address
    bt_socket = connect_bluetooth(mac_address, DATA_CHANNEL_ID)
    if not bt_socket:
        print("Failed to connect to Bluetooth device. Exiting...")
        return

    # Create the TCP server socket
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, lambda sig, frame: graceful_shutdown(bt_socket, tcp_socket))
    signal.signal(signal.SIGTERM, lambda sig, frame: graceful_shutdown(bt_socket, tcp_socket))

    # Start the TCP server and wait for client connections
    start_tcp_server(bt_socket, tcp_socket)



if __name__ == "__main__":
    main()
