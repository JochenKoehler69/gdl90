from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.factory import Factory
from kivy.properties import ObjectProperty
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.core.window import Window
from enum import Enum
import gdl90.listener as listener

import time


# Parameter, die später in Settings eingestellt werden können
SET_HOST=''
SET_PORT=4000
#SET_PORT=43211

class LoadDialog(FloatLayout): # Dialog zum Laden von aufgezeichneten Daten
    load = ObjectProperty(None)
    cancel = ObjectProperty(None)


class OpenDialog(FloatLayout): # Dialog zum Öffnen / Erzeugen eines Aufzeichnungsfiles
    open = ObjectProperty(None)
    text_input = ObjectProperty(None)
    cancel = ObjectProperty(None)

class enum_Workmode(Enum):
    Recording = 1
    Replaying = 2

class enum_Filetype(Enum):
    cap = enum_Workmode.Recording.value
    csv = enum_Workmode.Replaying.value

class enum_Status(Enum):
    Stopped = 1
    Paused = 2
    Running = 3

class Root(FloatLayout):
    Mode = enum_Workmode(1)
    Status = enum_Status(1)
    loadfile = ObjectProperty(None)
    lastUpdate = time.time()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Window.bind(on_request_close=self.on_request_close)
        self.Listener = listener.ListenerThread(parent=self, host=SET_HOST, port=SET_PORT)
        if self.Mode == enum_Workmode.Recording:
            # Gleich mal den Port mithorchen
            self.Listener.start()
            self.record_Event = Clock.schedule_interval(self.on_schedule_Recording, 2.0)

    def on_schedule_Recording(self, dt):
        difftime = time.time() - self.lastUpdate
        self.ids["label_lastupdate"].text = "[b] upated %3.2f seconds ago [/b]" % (difftime)

    def on_GDL90_newdata(self, callsign, datetime, speed, altitude, heading, lat, long):
        self.ids["value_callsign"].text = callsign
        self.ids["value_time"].text = str(datetime)
        self.ids["value_speed"].text = "%3.0f kts" % (speed)
        self.ids["value_altitude"].text = "%5.0f ft" % (altitude)
        self.ids["value_heading"].text = "%3.0f °" % (heading)
        self.ids["value_pos"].text = "%3.3f / %3.3f" % ((lat, long))
        self.lastUpdate = time.time()

    def dismiss_popup(self):
        self._popup.dismiss()

    def autostop_click(self):
        print("Autostop clicked")

    def start_stop(self):
        if self.Mode == enum_Workmode.Recording:
            if self.Status == enum_Status.Stopped:
                # Recording initiieren
                # 0. Nach Zieldatei fragen
                content = OpenDialog(open=self.open, cancel=self.dismiss_popup)
                self._popup = Popup(title="Open for Recording", content=content,
                                    size_hint=(0.9, 0.9))
                self._popup.open()
            else:
                self.Status = enum_Status.Stopped
                self.Listener.stopRecording()
                self.ids["btn_status"].text = "Stopped (Press to start recording)"
        else: # Mode == Replaying
            if self.Status == enum_Status.Paused:
                # Abzuspielendes File abfragen
                content = LoadDialog(load=self.load, cancel=self.dismiss_popup)
                self._popup = Popup(title="Choose file to be replayed", content=content,
                            size_hint=(0.9, 0.9))
                self._popup.open()
                # 1. Datei öffnen
                # 2. Replay starten
            else: # Status == Running
                self.Status = enum_Status.Paused
                # Replay anhalten

    def toggle_mode(self):
        if self.Mode == enum_Workmode.Recording:
            self.Listener.stop()
            self.Mode = enum_Workmode.Replaying
        else:
            self.Listener.start()
            self.Mode = enum_Workmode.Recording
        self.ids["btn_workmode"].text = self.Mode.name
        print("Mode toggled to: %s" % (self.Mode))

    def open(self, path, filename):
        self.dismiss_popup()
        print('Selected file: %s' % (filename))
        self.ids["label_filename"].text = filename    
        self.Status = enum_Status.Running    
        self.ids["btn_status"].text = "Recording (Press to stop)"
        print("Status toggled to %s" % (self.Status))
        # Aufzeichnen im Listener-Thread aktivieren
        self.Listener.startRecording(filepath = filename)

    def load(self, path, filename):
        self.dismiss_popup()
        print('Selected file: %s' % (path+filename))
        self.ids["label_filename"].text = path+filename
        self.Status = enum_Status.Running
        self.ids["btn_status"].text = "Replaying (Press to stop)"
        print("Status toggled to %s" % (self.Status))

 
    def on_request_close(self, *args):
        # self.Listener.stop()
        self.Listener.raise_exception()
        self.Listener.join()
        return False

class main(App):
    pass

Factory.register('Root', cls=Root)
Factory.register('OpenDialog', cls=OpenDialog)
Factory.register('LoadDialog', cls=LoadDialog)

if __name__ == '__main__':
    main().run()
