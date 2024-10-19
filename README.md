### Installation and Use

1. Clone the repository:
   
   ```sh
   git clone https://github.com/TheCommsChannel/Bluetooth-KISS-TCP-Server.git
   cd Bluetooth-KISS-TCP-Server
   ```

   If you don't have git, you can also download the zip file, unzip it, and navigate to the directory of the unzipped folder using command prompt and follow along with the rest.

2. Set up a Python virtual environment:  
   
   ```sh
   python -m venv venv
   ```

3. Activate the virtual environment:  
     
   ```sh
   venv\Scripts\activate  
   ```

4. Install the required packages:  
   
   ```sh
   pip install bleak
   ```

5. Start the server:  

   If you haven't already, pair your radio to your computer via Bluetooth and proceed to the next step
   
   ```sh
   python.exe server.py
   ```

   The script should connect to the radio and start a TCP server on port 8001.

6. Connect via software:  

   You should now be able to setup your software like PinPoint APRS that supports TNCs over TCP/IP by using and IP address of 127.0.0.1 and port 8001


### Use after closing

1. Starting the script:
   Each time you want to start the script again, you'll want to navigate to the script directoty from the command prompt and enter in the Python virtual environment by running the following command:
   
   ```sh
   venv\Scripts\activate  
   ```

2. Start the server:  

   If you haven't already, pair your radio to your computer via Bluetooth and then run the script
   
   ```sh
   python.exe server.py
   ```


## Thanks

Big thanks to [NA7Q](https://github.com/na7q/Bluetooth-KISS-TCP-Server) for the origial work on this.
