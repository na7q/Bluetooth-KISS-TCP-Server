import socket
import threading
import asyncio
from bleak import BleakScanner
import os
import signal
from threading import Event

# Bluetooth connection settings
DEVICE_NAMES = ["UV-PRO", "VR-N76", "GA-5WB"]  # List with possible device names
DATA_CHANNEL_ID = 3  # Replace with your device's RFCOMM channel

# TCP Server settings
TCP_HOST = '0.0.0.0'  # Listen on all interfaces
TCP_PORT = 8001  # TCP port number

# Create a global shutdown event
shutdown_event = Event()


async def find_bluetooth_device(device_name_list, scan_retries=3, scan_timeout=10):
    """
    Scan for Bluetooth devices and return the MAC address of the first matching device name.
    Allows partial name matching and retrying if the device is not found.

    Args:
        device_name_list (list): List of possible device names to match.
        scan_retries (int): Number of times to retry the scan.
        scan_timeout (int): Timeout in seconds for each scan attempt.

    Returns:
        str or None: The MAC address of the found device or None if not found.
    """
    for attempt in range(scan_retries):
        print(f"Scanning for Bluetooth devices (Attempt {attempt + 1}/{scan_retries})...")

        try:
            devices = await BleakScanner.discover(timeout=scan_timeout)

            for device in devices:
                print(f"Found Bluetooth device: {device.name} - {device.address}")
                for device_name in device_name_list:
                    # Use partial matching (case-insensitive)
                    if device.name and device_name.lower() in device.name.lower():
                        print(f"Matched device '{device.name}' with {device_name}.")
                        return device.address

            print(f"No matching devices found in this attempt.")

        except Exception as e:
            print(f"Error during Bluetooth scan: {e}")

    print(f"Failed to find any matching Bluetooth device after {scan_retries} attempts.")
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

    # Attempt to find a Bluetooth device from the list of names with improved search
    mac_address = asyncio.run(find_bluetooth_device(DEVICE_NAMES))

    if not mac_address:
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
