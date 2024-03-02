#
# listener.py
#

import os, sys, socket, time
import gdl90.decoder as decoder
import threading
import ctypes


# Default values for options
DEF_RECV_MAXSIZE=1500
DEF_DATA_FLUSH_SECS=10


class ListenerThread(threading.Thread):
    def __init__(self, parent, host, port, **kwargs):
        super().__init__(**kwargs)
        self._stop_event = threading.Event()
        self.decoder = decoder.Decoder()
        self.decoder.format = "plotflight"
        self.isInitialized = False
        self.host = host
        self.port = port
        self.parent = parent
        self.logFile = None
        try:
            self.sockIn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sockIn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            #self.sockIn.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.init()
        except Exception as e:
            print(e, sys.stderr)

    def init(self):
        self.sockIn.bind((self.host, self.port))
        self.packetTotal = 0
        self.bytesTotal = 0
        self.lastFlushTime = time.time()
        self.isInitialized = True   

    def startRecording(self, filepath, autostop = False):
        try:
            # 1. Datei öffnen
            self.logFile = open(filepath, "wb") # "b" steht für Binary!
        except Exception as e:
            print(e, sys.stderr)

    
    def run(self):
        try:
            if not self.isInitialized:
                self.init()
            while True:
                (data, dataSrc) = self.sockIn.recvfrom(DEF_RECV_MAXSIZE)
                self.packetTotal += 1
                self.bytesTotal += len(data)
                if not self.logFile is None and not self.logFile.closed:
                    self.logFile.write(data)
                    # Ensure periodic flush to disk
                    if int(time.time() - self.lastFlushTime) > 10.0:
                        self.logFile.flush()
                        os.fsync(self.logFile.fileno())
                        self.lastFlushTime = time.time()
                # Display read data
                self.decoder.addBytes(data)
                self.parent.on_GDL90_newdata(self.decoder.callsign, self.decoder.currtime, self.decoder.speed, self.decoder.altitude, self.decoder.heading, self.decoder.latitude, self.decoder.longitude)
        except Exception as e:
            print(e, sys.stderr)
        finally:
            self.stop()
            print("Stop listening to GDL90")


    def stopRecording(self):
        # Recording anhalten
        if not self.logFile is None and not self.logFile.closed:
            self.logFile.close()
            self.logFile = None


    def stop(self):
        self._stop_event.set()
        self.sockIn.close()
        self.isInitialized = False


    def get_id(self):
        # returns id of the respective thread
        if hasattr(self, '_thread_id'):
            return self._thread_id
        for id, thread in threading._active.items():
            if thread is self:
                return id
            
    def raise_exception(self):
        thread_id = self.get_id()
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, ctypes.py_object(SystemExit))
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
