from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.factory import Factory
from kivy.properties import ObjectProperty
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.core.window import Window
from enum import Enum
import gdl90.listener as listener

import os, time


# Parameter, die später in Settings eingestellt werden können
SET_HOST=''
#SET_PORT=4000
SET_PORT=43211

class LoadDialog(FloatLayout): # Dialog zum Laden von aufgezeichneten Daten
    load = ObjectProperty(None)
    cancel = ObjectProperty(None)

class OpenDialog(FloatLayout): # Dialog zum Öffnen / Erzeugen eines Aufzeichnungsfiles
    open = ObjectProperty(None)
    text_input = ObjectProperty(None)
    cancel = ObjectProperty(None)

class SelectDirDialog(FloatLayout): # Dialog zum Öffnen / Erzeugen eines Aufzeichnungsfiles

    select = ObjectProperty(None)
    cancel = ObjectProperty(None)

class SettingsDialog(FloatLayout): # Dialog für Settings - Record
    changeSettings = ObjectProperty(None)
    cancel = ObjectProperty(None)

    def dismiss_popup(self):
        self._popup.dismiss()

    def select(self, DirName):
        self._popup.dismiss()
        self.ids["btn_DirName"].text = DirName 

    def selectDir(self):
        content = SelectDirDialog(select=self.select, cancel=self.dismiss_popup)
        self._popup = Popup(title="Choose Default Directory", content=content, size_hint=(0.9, 0.9))
        self._popup.open()
        content.ids["fdirchooser"].path = self.ids["btn_DirName"].text

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

class MainWin(FloatLayout):
    Mode = enum_Workmode(1)
    Status = enum_Status(1)
    loadfile = ObjectProperty(None)
    lastUpdate = time.time()
    AutoStopRecording = True
    AutoRecordName = False
    ActiveSender = False
    TimeToWaitUntilStop = 600
    diffTime = 0
    DirName = './'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Window.bind(on_request_close=self.on_request_close)
        self.Listener = listener.ListenerThread(parent=self, host=SET_HOST, port=SET_PORT)
        if self.Mode == enum_Workmode.Recording:
            # Gleich mal den Port mithorchen
            self.Listener.start()
            self.record_Event = Clock.schedule_interval(self.on_schedule_Listening, 2.0)

    def on_schedule_Listening(self, dt):
        self.diffTime = time.time() - self.lastUpdate
        self.ids["label_lastupdate"].text = "[b] upated %3.1f seconds ago [/b]" % (self.diffTime)
        if self.ActiveSender and self.diffTime > self.TimeToWaitUntilStop:
            self.ActiveSender = False            
            if self.Status == enum_Status.Running and self.AutoStopRecording:
                # Recording stoppen
                self.stopRecording()
            self.setStatusButton()

    def startRecording(self, filename):
        print('Selected file: %s' % (filename))
        self.ids["label_filename"].text = filename    
        self.Status = enum_Status.Running    
        self.setStatusButton()
        print("Status toggled to %s" % (self.Status))
        # Aufzeichnen im Listener-Thread aktivieren
        self.Listener.startRecording(filepath = filename)

    def stopRecording(self):
        self.Status = enum_Status.Stopped
        self.Listener.stopRecording()
        self.ids["label_filename"].text = "No file selected"
        self.setStatusButton()

    def on_GDL90_newdata(self, callsign, datetime, speed, altitude, heading, lat, long):
        if not self.ActiveSender:
            self.ActiveSender = True
            self.setStatusButton()
        self.ids["value_callsign"].text = callsign
        self.ids["value_time"].text = str(datetime)
        self.ids["value_speed"].text = "%3.0f kts" % (speed)
        self.ids["value_altitude"].text = "%5.0f ft" % (altitude)
        self.ids["value_heading"].text = "%3.0f °" % (heading)
        self.ids["value_pos"].text = "%3.3f / %3.3f" % ((lat, long))
        self.lastUpdate = time.time()

    def setStatusButton(self):
        if self.Status == enum_Status.Running:
            # Es wird aufgenommen
            if self.ActiveSender:
                self.ids["btn_status"].text = "Recording (Press to stop)"
                self.ids["btn_status"].background_color=[1,0,0,1]
            else:
                self.ids["btn_status"].text = "Recording - But no data (Press to stop)" 
                self.ids["btn_status"].background_color=[1, 127/255, 127/255,1]
        else:
            if self.ActiveSender:       
                self.ids["btn_status"].text = "Stopped (Press to start recording)"
                self.ids["btn_status"].background_color=[1, 20/255, 20/255,1]
            else:
                self.ids["btn_status"].text = "Receiving no data to be recorded"
                self.ids["btn_status"].background_color=[127/255, 127/255, 127/255,1]

    def dismiss_popup(self):
        self._popup.dismiss()

    def nextFileName(self, baseName='gdl90_cap', fmt=r'%s/%s.%03d'):
        if not os.path.isdir(self.DirName):
            Exception("Directory %s does not exist" % (self.DirName))
        i = 0
        while i < 1000:
            fname = fmt % (self.DirName, baseName, i)
            if not os.path.exists(fname):
                return os.path.abspath(fname)
            i += 1
        raise Exception("Search exhausted; too many files exist already.")

    def start_stop(self):
        if self.Mode == enum_Workmode.Recording:
            if self.Status == enum_Status.Stopped:
                if self.ActiveSender:
                    # Recording initiieren
                    # 0. Nach Zieldatei fragen
                    if self.AutoRecordName:
                        self.startRecording(self.nextFileName())
                    else:
                        content = OpenDialog(open=self.openFromDialog, cancel=self.dismiss_popup)
                        self._popup = Popup(title="Open for Recording", content=content,
                                            size_hint=(0.9, 0.9))
                        self._popup.open()
                        content.ids["filechooser"].path = self.DirName
            else:
                self.stopRecording()
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

    def settings(self):
        content = SettingsDialog(changeSettings=self.changeSettings, cancel=self.dismiss_popup)
        self._popup = Popup(title="Settings", content=content, size_hint=(0.9, 0.9))
        self._popup.open()
        # Erst mal Werte befüllen
        content.ids["checkbox_AutoRecordName"].active = self.AutoRecordName
        content.ids["checkbox_Autostop"].active = self.AutoStopRecording
        content.ids["text_WaitUntilAutostop"].text = "%i" % (self.TimeToWaitUntilStop)
        content.ids["btn_DirName"].text = self.DirName

    def openFromDialog(self, path, filename):
        self.dismiss_popup()
        self.startRecording(os.path.abspath(filename))

    def load(self, path, filename):
        self.dismiss_popup()
        print('Selected file: %s' % (path+filename))
        self.ids["label_filename"].text = path+filename
        self.Status = enum_Status.Running
        self.ids["btn_status"].text = "Replaying (Press to stop)"
        print("Status toggled to %s" % (self.Status))

    def changeSettings(self, DirName, AutoName, AutoStopRecording, TimeToWait):
        self.dismiss_popup()
        self.DirName = DirName
        self.AutoRecordName = AutoName
        self.AutoStopRecording = AutoStopRecording
        self.TimeToWaitUntilStop = int(TimeToWait) 

    def on_request_close(self, *args):
        self.Listener.stop()
        self.Listener.raise_exception()
        self.Listener.join()
        return False

class main(App):
    pass

Factory.register('MainWin', cls=MainWin)
Factory.register('OpenDialog', cls=OpenDialog)
Factory.register('LoadDialog', cls=LoadDialog)
Factory.register('SettingsDialog', cls=SettingsDialog)
Factory.register('SelectDirDialog', cls=SelectDirDialog)

if __name__ == '__main__':
    main().run()
