import socket
import threading
import asyncio
from bleak import BleakScanner
import os
import signal
from threading import Event
import tkinter as tk
from tkinter import messagebox, Listbox, END
import concurrent.futures

# Bluetooth connection settings
DEVICE_NAMES = ["UV-PRO", "VR-N76", "GA-5WB"]  # List with possible device names
DATA_CHANNEL_ID = 3  # Replace with your device's RFCOMM channel

# TCP Server settings
TCP_HOST = '0.0.0.0'  # Listen on all interfaces
TCP_PORT = 8001  # TCP port number

# Create a global shutdown event
shutdown_event = Event()
bt_socket = None
tcp_socket = None
tcp_thread = None

def is_valid_mac(mac):
    """Check if the given MAC address is valid."""
    if len(mac) != 17:
        return False
    if not all(c in '0123456789ABCDEFabcdef:' for c in mac):
        return False
    return True

def update_start_button_state(*args):
    """Enable or disable the Start Server button based on the MAC address validity."""
    mac = mac_entry.get()
    if is_valid_mac(mac):
        start_button.config(state=tk.NORMAL)
    else:
        start_button.config(state=tk.DISABLED)
    

async def scan_bluetooth_devices():
    """Scan for Bluetooth devices asynchronously and return the list."""
    print("Scanning for Bluetooth devices...")
    devices = await BleakScanner.discover()
    return devices


def connect_bluetooth(mac_address, channel):
    """Establish Bluetooth socket connection using RFCOMM protocol."""
    global bt_socket
    try:
        bt_sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        bt_sock.connect((mac_address, channel))
        print(f"Connected to {mac_address} on channel {channel}")
        
        # Update listbox to show Bluetooth device connected
        update_device_list_with_status(mac_address, "[Connected]")

        # Inside your connection logic after successfully connecting
        if mac_address:
            save_last_mac_address(mac_address)  # Save the MAC address after a successful connection                
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
        
        # Update listbox to show TCP server running
        update_device_list_with_status("TCP Server", "[Running]")

        while not shutdown_event.is_set():
            try:
                client_sock, client_address = tcp_sock.accept()  # Accept TCP client connection
                print(f"Client connected from {client_address}")

                # Add connected client to the listbox
                update_device_list_with_status(f"Client {client_address}", "[Connected]")

                # Create separate daemon threads to handle Bluetooth <-> TCP data transfer
                bt_to_tcp_thread = threading.Thread(target=handle_bt_to_tcp, args=(bt_sock, client_sock), daemon=True)
                tcp_to_bt_thread = threading.Thread(target=handle_tcp_to_bt, args=(client_sock, bt_sock), daemon=True)

                bt_to_tcp_thread.start()
                tcp_to_bt_thread.start()
            except socket.timeout:
                continue  # Timeout occurred, loop again to check for shutdown_event
            except OSError as e:
                # Handle socket closure gracefully
                print(f"TCP Server error (likely due to shutdown): {e}")
                break

    except Exception as e:
        print(f"TCP Server setup error: {e}")

def handle_bt_to_tcp(bt_sock, client_sock):
    """Forward data from Bluetooth to the TCP client."""
    try:
        bt_sock.settimeout(1.0)
        while not shutdown_event.is_set():
            try:
                data = bt_sock.recv(1024)
                if data:
                    print(f"Received from Bluetooth: {data}")
                    client_sock.sendall(data)  # Send the data to the TCP client
            except socket.timeout:
                continue
    except Exception as e:
        print(f"Error forwarding Bluetooth to TCP: {e}")
    finally:
        client_sock.close()


def handle_tcp_to_bt(client_sock, bt_sock):
    """Forward data from the TCP client to the Bluetooth device."""
    try:
        client_sock.settimeout(1.0)
        while not shutdown_event.is_set():
            try:
                data = client_sock.recv(1024)
                if data:
                    print(f"Received from TCP client: {data}")
                    bt_sock.sendall(data)  # Send the data to the Bluetooth device
            except socket.timeout:
                continue
    except Exception as e:
        print(f"Error forwarding TCP to Bluetooth: {e}")
    finally:
        client_sock.close()


def graceful_shutdown():
    """Shut down Bluetooth and TCP sockets gracefully without exiting the application."""
    global bt_socket, tcp_socket

    print("Shutting down Bluetooth and TCP server...")
    shutdown_event.set()  # Signal threads to stop

    # Safely close the Bluetooth socket if it's still open
    if bt_socket:
        try:
            bt_socket.close()
            print("Bluetooth socket closed.")
            update_device_list_with_status("Bluetooth Device", "[Disconnected]")  # Update status
        except Exception as e:
            print(f"Error closing Bluetooth socket: {e}")

    # Safely close the TCP socket if it's still open
    if tcp_socket:
        try:
            # Check if the socket is connected before shutting it down
            tcp_socket.shutdown(socket.SHUT_RDWR)
            tcp_socket.close()
            print("TCP server socket closed.")
            update_device_list_with_status("TCP Server", "[Stopped]")  # Update status
        except OSError as e:
            if e.errno == 10057:  # This means the socket was not connected
                print("TCP socket is not connected or already closed.")
            else:
                print(f"Error closing TCP server socket: {e}")
        except Exception as e:
            print(f"Unexpected error while closing TCP server socket: {e}")
            
def on_closing():
    """Handle the window close event (X button) and ensure a clean exit."""
    if bt_socket or tcp_socket:
        # If the server is running, stop it before exiting
        graceful_shutdown()
    root.destroy()  # Close the Tkinter window and exit the program


def stop_server():
    """Trigger a graceful shutdown of Bluetooth and TCP server but keep the GUI running."""
    graceful_shutdown()

# Add this function to handle Listbox selection
def on_device_select(event):
    """Handle the selection of a device from the Listbox."""
    try:
        # Get the selected device entry
        selected_device = device_listbox.get(device_listbox.curselection())
        # Extract the MAC address from the selected entry
        selected_mac = selected_device.split(" - ")[1]  # Assuming the format is "Name - MAC Address"
        # Populate the MAC entry with the selected MAC address
        mac_entry.delete(0, tk.END)  # Clear the entry first
        mac_entry.insert(0, selected_mac)  # Insert the selected MAC address
    except tk.TclError:
        pass  # Handle the case where there is no selection


# Tkinter GUI functions

def start_server():
    global bt_socket, tcp_socket, tcp_thread

    selected_mac = mac_entry.get()  # Get MAC address from the entry field

    if not selected_mac:
        try:
            # Get selected MAC address from the listbox
            selected_device = device_listbox.get(device_listbox.curselection())
            selected_mac = selected_device.split(" - ")[1]
        except tk.TclError:
            messagebox.showerror("Error", "No device selected.")
            return

    # Connect to the Bluetooth device
    bt_socket = connect_bluetooth(selected_mac, DATA_CHANNEL_ID)
    if not bt_socket:
        messagebox.showerror("Error", "Failed to connect to Bluetooth device.")
        return

    # Create the TCP server socket
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Start the TCP server thread
    tcp_thread = threading.Thread(target=start_tcp_server, args=(bt_socket, tcp_socket), daemon=True)
    tcp_thread.start()
    start_button.config(state=tk.DISABLED)
    stop_button.config(state=tk.NORMAL)

def async_scan_devices():
    """Wrapper to scan Bluetooth devices in a separate thread."""
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(asyncio.run, scan_bluetooth_devices())
        devices = future.result()
        update_device_list(devices)

def scan_devices():
    """Scan for Bluetooth devices and display them in the listbox."""
    # Show scanning message
    device_listbox.delete(0, END)  # Clear existing devices
    device_listbox.insert(END, "Scanning...")  # Add scanning message
    scan_button.config(state=tk.DISABLED)  # Disable the scan button
    
    device_listbox.update()  # Update the Listbox to reflect the change

    async_scan_devices()  # Start scanning in a separate thread

def save_last_mac_address(mac_address):
    """Save the last used MAC address to a file."""
    with open("last_mac_address.txt", "w") as f:
        f.write(mac_address)

def load_last_mac_address():
    """Load the last used MAC address from a file."""
    try:
        with open("last_mac_address.txt", "r") as f:
            mac_address = f.read().strip()
            return mac_address
    except FileNotFoundError:
        return None  # Return None if the file does not exist

def update_device_list_with_status(device_info, status):
    """Update the listbox with the device status."""
    device_listbox.insert(END, f"{device_info} {status}")

def update_device_list(devices):
    """Update the listbox with the scanned devices."""
    device_listbox.delete(0, END)  # Clear the scanning message    
    if devices:
        for device in devices:
            if device.name:
                device_listbox.insert(END, f"{device.name} - {device.address}")
    else:
        device_listbox.insert(END, "No devices found")

    # Re-enable the scan button after updating the device list
    scan_button.config(state=tk.NORMAL)  # Enable the scan button

# Create the GUI application
root = tk.Tk()
root.title("Bluetooth TCP Forwarder")

# Define the MAC address entry field
mac_label = tk.Label(root, text="MAC Address:")
mac_label.pack()

mac_entry = tk.Entry(root, width=40)
mac_entry.pack()
mac_entry.bind("<KeyRelease>", update_start_button_state)  # Bind key release event

# Load the last used MAC address
last_mac_address = load_last_mac_address()

# If there's a last MAC address, set it in the entry widget
if last_mac_address:
    mac_entry.delete(0, tk.END)  # Clear the entry first
    mac_entry.insert(0, last_mac_address)  # Insert the last used MAC address


# Define the listbox for Bluetooth devices
device_label = tk.Label(root, text="Available Bluetooth Devices:")
device_label.pack()

device_listbox = Listbox(root, width=50, height=10)
device_listbox.pack()

# Bind the selection event to the Listbox
device_listbox.bind('<<ListboxSelect>>', on_device_select)  # Bind selection event

# Add scan button
scan_button = tk.Button(root, text="Scan for Devices", command=scan_devices)
scan_button.pack()

# Add start and stop buttons
start_button = tk.Button(root, text="Start Server", command=start_server)
start_button.pack(pady=10)

stop_button = tk.Button(root, text="Stop Server", command=stop_server, state=tk.DISABLED)
stop_button.pack()

# Start the Tkinter event loop
root.protocol("WM_DELETE_WINDOW", on_closing)

root.mainloop()
