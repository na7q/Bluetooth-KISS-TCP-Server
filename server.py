import socket
import threading
import asyncio
from bleak import BleakScanner
import os

# Bluetooth connection settings
DEVICE_NAME = "UV-PRO"  # Replace with your Bluetooth device name
DATA_CHANNEL_ID = 3      # Replace with your device's RFCOMM channel

# TCP Server settings
TCP_HOST = '0.0.0.0'  # Listen on all interfaces
TCP_PORT = 8001       # TCP port number

# File to store the MAC address
MAC_FILE = 'device_mac.txt'

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

def save_mac_address(mac_address):
    """Save the MAC address to a file."""
    with open(MAC_FILE, 'w') as f:
        f.write(mac_address)
    print(f"MAC address saved: {mac_address}")

def load_mac_address():
    """Load the MAC address from a file if it exists."""
    if os.path.exists(MAC_FILE):
        with open(MAC_FILE, 'r') as f:
            mac_address = f.read().strip()
            print(f"Loaded MAC address from file: {mac_address}")
            return mac_address
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

def start_tcp_server(bt_sock):
    """Start a TCP server that forwards data between TCP clients and Bluetooth socket."""
    try:
        # Create TCP server socket
        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_sock.bind((TCP_HOST, TCP_PORT))
        tcp_sock.listen(1)  # Allow only 1 client at a time
        print(f"TCP server started on port {TCP_PORT}. Waiting for client connection...")

        while True:
            client_sock, client_address = tcp_sock.accept()  # Accept TCP client connection
            print(f"Client connected from {client_address}")

            # Create separate threads to handle Bluetooth <-> TCP data transfer
            threading.Thread(target=handle_bt_to_tcp, args=(bt_sock, client_sock)).start()
            threading.Thread(target=handle_tcp_to_bt, args=(client_sock, bt_sock)).start()

    except Exception as e:
        print(f"TCP Server error: {e}")

def handle_bt_to_tcp(bt_sock, client_sock):
    """Forward data from Bluetooth to the TCP client."""
    try:
        while True:
            data = bt_sock.recv(1024)  # Receive data from Bluetooth device
            if data:
                print(f"Received from Bluetooth: {data}")
                client_sock.sendall(data)  # Send the data to the TCP client
    except Exception as e:
        print(f"Error forwarding Bluetooth to TCP: {e}")
        client_sock.close()

def handle_tcp_to_bt(client_sock, bt_sock):
    """Forward data from the TCP client to the Bluetooth device."""
    try:
        while True:
            data = client_sock.recv(1024)  # Receive data from TCP client
            if data:
                print(f"Received from TCP client: {data}")
                bt_sock.sendall(data)  # Send the data to the Bluetooth device
    except Exception as e:
        print(f"Error forwarding TCP to Bluetooth: {e}")
        client_sock.close()

def main():
    # Load MAC address from file, or scan if it doesn't exist
    mac_address = load_mac_address()
    
    if not mac_address:
        # Connect to the Bluetooth device
        mac_address = asyncio.run(find_bluetooth_device(DEVICE_NAME))

        if not mac_address:
            print("Failed to find Bluetooth device. Exiting...")
            return
        
        # Save the found MAC address to file
        save_mac_address(mac_address)

    # Connect to the Bluetooth device using the found MAC address
    bt_socket = connect_bluetooth(mac_address, DATA_CHANNEL_ID)

    if not bt_socket:
        print("Failed to connect to Bluetooth device. Exiting...")
        return

    # Start the TCP server and wait for client connections
    start_tcp_server(bt_socket)

if __name__ == "__main__":
    main()
