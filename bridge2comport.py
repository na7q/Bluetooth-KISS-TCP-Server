import socket
import threading
import asyncio
from bleak import BleakScanner
import os
import signal
from threading import Event
import serial  # pyserial for virtual COM port

# Bluetooth connection settings
DEVICE_NAMES = ["UV-PRO", "VR-N76", "GA-5WB"]  # List with possible device names
DATA_CHANNEL_ID = 3  # Replace with your device's RFCOMM channel

# Serial port settings
VIRTUAL_COM_PORT = 'COM8'  # Adjust to the virtual COM port you're using
BAUD_RATE = 9600  # Adjust as necessary for your setup

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


def start_serial_bridge(bt_sock, serial_port):
    """Start the serial bridge that forwards data between the Bluetooth socket and a virtual COM port."""
    try:
        while not shutdown_event.is_set():
            bt_to_serial_thread = threading.Thread(target=handle_bt_to_serial, args=(bt_sock, serial_port), daemon=True)
            serial_to_bt_thread = threading.Thread(target=handle_serial_to_bt, args=(serial_port, bt_sock), daemon=True)

            bt_to_serial_thread.start()
            serial_to_bt_thread.start()

            # Wait for both threads to finish (which may never happen unless there's an error)
            bt_to_serial_thread.join()
            serial_to_bt_thread.join()

    except Exception as e:
        print(f"Serial Bridge error: {e}")


def handle_bt_to_serial(bt_sock, serial_port):
    """Forward data from Bluetooth to the serial port."""
    try:
        bt_sock.settimeout(1.0)  # Set a timeout to allow periodic checks for shutdown_event
        while not shutdown_event.is_set():
            try:
                data = bt_sock.recv(1024)  # Receive data from Bluetooth device
                if data:
                    print(f"Received from Bluetooth: {data}")
                    serial_port.write(data)  # Send the data to the virtual COM port
            except socket.timeout:
                continue  # Timeout occurred, loop again to check for shutdown_event
    except Exception as e:
        print(f"Error forwarding Bluetooth to serial: {e}")


def handle_serial_to_bt(serial_port, bt_sock):
    """Forward data from the virtual COM port to the Bluetooth device."""
    try:
        while not shutdown_event.is_set():
            if serial_port.in_waiting > 0:
                data = serial_port.read(serial_port.in_waiting)  # Receive data from virtual COM port
                if data:
                    print(f"Received from serial: {data}")
                    bt_sock.sendall(data)  # Send the data to the Bluetooth device
    except Exception as e:
        print(f"Error forwarding serial to Bluetooth: {e}")


def graceful_shutdown(bt_sock, serial_port=None):
    print("Shutting down gracefully...")
    shutdown_event.set()  # Signal all threads to stop
    if bt_sock:
        bt_sock.close()
        print("Bluetooth socket closed.")
    if serial_port:
        serial_port.close()
        print("Serial port closed.")
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

    # Open the virtual COM port
    try:
        serial_port = serial.Serial(VIRTUAL_COM_PORT, BAUD_RATE, timeout=1)
        print(f"Opened virtual COM port {VIRTUAL_COM_PORT} at baud rate {BAUD_RATE}")
    except Exception as e:
        print(f"Failed to open virtual COM port: {e}")
        return

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, lambda sig, frame: graceful_shutdown(bt_socket, serial_port))
    signal.signal(signal.SIGTERM, lambda sig, frame: graceful_shutdown(bt_socket, serial_port))

    # Start the serial bridge and wait for data transfers
    start_serial_bridge(bt_socket, serial_port)


if __name__ == "__main__":
    main()
