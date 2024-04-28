#!/usr/bin/env python
#
# simulate_GarminFromFile.py
#


import time
import timesetter
from datetime import datetime, timezone, timedelta
import socket
import gdl90.encoder
import os
import sys
import optparse
from pygame import mixer
from collections import namedtuple
import gpxpy
import gpxpy.gpx
import math

__progTitle__ = "GDL-90 Sender"

__author__ = "Jochen Koehler"
__created__ = "Januar 2024"
__copyright__ = "Copyright (c) 2025 by Jochen Koehler"

__date__ = "$Date$"
__version__ = "0.1"
__revision__ = "$Revision$"
__lastChangedBy__ = "$LastChangedBy$"

#################
# We have some ambiguities due to non-smooth input data. Possible improvement by calculating a gliding average value - 
# but this ends up in more complex code ...

# Default values for options
DEF_SEND_ADDR="255.255.255.255"
DEF_SEND_PORT=43211
# DEF_SEND_PORT=4000

# Date-Format
datetime_format = '%Y-%m-%d %H:%M:%S %z'
time_format = '%H:%M:%S'
opt_starttime = None
opt_endtime = None

m_to_ft = 3.28
mps_to_kt = 3.6/1.852 

# Exit codes
EXIT_CODE = {
    "OK" : 0,
    "OPTIONS" : 1,
    "OTHER" : 99,
}
   
def print_error(msg):
    """print an error message"""
    print(sys.stderr, msg)

def simulateIt(filename, callSign='', offsetstart=0, duration=18000, takeoff_altitude=-2000.0, landing_altitude=-2000.0, dest="255.255.255.255", 
               port=43211, starttimeStr='', endtimeStr='', logfile=0):
    print("Simulating Skyradar from Skydemon GPX File")
    print("Transmitting to %s:%s" % (dest, port))
    StartTime = None
    EndTime = None
    if not starttimeStr == '':
        StartTime = datetime.strptime(starttimeStr, time_format).time().replace(tzinfo=timezone.utc)
        offsetstart = 0
    if not endtimeStr == '':
        EndTime = datetime.strptime(endtimeStr, time_format).time().replace(tzinfo=timezone.utc)
        duration = 18000

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    packetTotal = 0
    FirstIt = True
    encoder = gdl90.encoder.Encoder()
    OffsetLandingAltitudeGPS = 0
    OffsetTakeOffAltitudeGPS = 0
    gradOffsetAltitudeGPS = 0
    lastdatetime = None
    TakeOffDetectedForOffset = False
    TimeSynced = False

    # Open log file if necessary
    if logfile > 0:
        log_file = open('logfile.txt', 'w')

    # GPX File öffnen
    gpx_file = open(filename, 'r')
    gpx = gpxpy.parse(gpx_file)
    # Create first track in our GPX:
    gpx_track = gpxpy.gpx.GPXTrack()
    # Create first segment in our GPX track:
    gpx_segment = gpxpy.gpx.GPXTrackSegment()
    gpx_track.segments.append(gpx_segment)
    for track in gpx.tracks:
        for segment in track.segments:
            # Erste Runde: Start und Landung finden und doppelte Punkte rausschmeissen
            for point in segment.points:
                groundspeed = point.speed*mps_to_kt
                logdatetime = point.time # richtiges Format rausfinden

                if lastdatetime is None:
                    lastdatetime = logdatetime
                else:
                    diffTime = logdatetime - lastdatetime
                    if diffTime.seconds < 1.1:
                        # diesen Punkt rausschmeissen
                        segment.points.remove(point)
                    lastdatetime = logdatetime                    
                if groundspeed > 40:
                    if not TakeOffDetectedForOffset:
                        if takeoff_altitude > -1000.0 and landing_altitude > - 1000.0:
                            OffsetTakeOffAltitudeGPS = takeoff_altitude - point.elevation*m_to_ft + 10
                        TakeOffTime = logdatetime
                        print("Takeoff at %s with altitude offset: %d" % (TakeOffTime.strftime('%H:%M:%S'), OffsetTakeOffAltitudeGPS))
                        TakeOffDetectedForOffset = True
                else:
                    if not TakeOffDetectedForOffset: 
                        continue
                    if TakeOffDetectedForOffset and groundspeed < 20:
                        LandingTime = logdatetime
                        if takeoff_altitude > -1000.0 and landing_altitude > - 1000.0:
                            OffsetLandingAltitudeGPS = landing_altitude - point.elevation*m_to_ft
                            gradOffsetAltitudeGPS = (OffsetLandingAltitudeGPS - OffsetTakeOffAltitudeGPS) / (LandingTime - TakeOffTime).total_seconds()
                        print("Landing at %s with altitude offset: %d" % (LandingTime.strftime('%H:%M:%S'), OffsetLandingAltitudeGPS))
                        break
            print("Flying Time: %s" % (LandingTime - TakeOffTime))

            # This is the second run
            num_points = 0
            dT = 0
            # save beginning of iteration
            startTimeIteration = time.time()
            for point in segment.points:
                try:
                    logdatetime = point.time
                    nextTimeSim = logdatetime.second + logdatetime.minute *60 + logdatetime.hour *3600
                    # Altitude correction
                    if TakeOffDetectedForOffset:
                        OffsetAltitudeGPS = OffsetTakeOffAltitudeGPS + gradOffsetAltitudeGPS * max(0.0, (min(logdatetime, LandingTime) - TakeOffTime).total_seconds())
                    else:
                        OffsetAltitudeGPS = 0
                    nextAltitude = point.elevation*m_to_ft + OffsetAltitudeGPS
                    nextGroundspeed = point.speed*mps_to_kt
                    nextLatitude = point.latitude
                    nextLongitude = point.longitude
                    nextLatrad = math.radians(nextLatitude)
                    nextLonrad = math.radians(nextLongitude)
                    if FirstIt:
                        nextVerticalspeed = 0 
                        nextTrack = 0.0
                        lastTrack = 0.0
                        timeSim = nextTimeSim
                        startTimeSim = timeSim
                        FirstIt = False
                        if StartTime is None:
                            StartTime = logdatetime + timedelta(seconds=offsetstart)
                        else:
                            # Zeit auf Datum draufrechnen
                            StartTime = datetime.combine(logdatetime.date(), StartTime)
                        if EndTime is None:
                            EndTime = logdatetime + timedelta(seconds=offsetstart) + timedelta(seconds=duration)
                        else:
                            # Zeit auf Datum draufrechnen
                            EndTime = datetime.combine(logdatetime.date(), EndTime)
                    else:
                        if logdatetime <= StartTime: # did we pass start time already?
                            timeSim = nextTimeSim
                            startTimeSim = timeSim
                            continue
                        elif logdatetime > EndTime: # is duration over already? 
                            break                        
                        dT = nextTimeSim - lastTimeSim
                        if dT < 0.1:
                            continue
                        nextVerticalspeed = (nextAltitude - lastAltitude) / dT * 60
                        try:
                            distance = math.acos(math.sin(lastLatrad)*math.sin(nextLatrad)+math.cos(lastLatrad)*math.cos(nextLatrad)*math.cos(min(0.0, max(1.0, nextLonrad-lastLonrad))))*6371 
                        except Exception as e:
                            prttext = "lastLatrad=%09.5f, nextLatrad=%09.5f, nextLonrad=%09.5f, nextLonrad=%09.5f" % (lastLatrad, nextLatrad, nextLonrad, nextLonrad)
                            print(prttext)
                            distance = 0.0
                            if logfile > 0:
                                log_file.write(prttext + "\n")

                        if nextGroundspeed > 0.5 and distance > 0.001:
                            X = math.cos(nextLatrad) * math.sin(nextLonrad-lastLonrad)
                            Y = math.cos(lastLatrad) * math.sin(nextLatrad) - math.sin(lastLatrad) * math.cos(nextLatrad) * math.cos(nextLonrad-lastLonrad)
                            if X == 0.0 and Y == 0.0:
                                continue
                            nextTrack = math.degrees(math.atan2(X,Y))
                            if nextTrack - lastTrack > 180.0:
                                lastTrack = lastTrack +360.0
                            else:
                                if nextTrack - lastTrack < -180.0:
                                    lastTrack = lastTrack -360.0
                        else:
                            if lastGroundspeed < 5.0:
                                nextGroundspeed = 0.0
                        while timeSim < nextTimeSim and dT > 0.5:
                            # timeStartLoop = time.time()  # mark start time - just for delay
                            timeSim = timeSim + 1.0

                            # Calculate intermediate step
                            intMult = (timeSim-lastTimeSim) / (nextTimeSim - lastTimeSim)
                            latitude = lastLatitude + (nextLatitude-lastLatitude) * intMult
                            longitude = lastLongitude + (nextLongitude-lastLongitude) * intMult
                            altitude = lastAltitude + (nextAltitude-lastAltitude) * intMult
                            groundspeed = lastGroundspeed + (nextGroundspeed-lastGroundspeed) * intMult
                            verticalspeed = lastVerticalspeed + (nextVerticalspeed-lastVerticalspeed) * intMult
                            track = lastTrack + (nextTrack-lastTrack) * intMult

                            if track < 0:
                                track = 360.0+track


                            # Heartbeat Message
                            buf = encoder.msgHeartbeat(ts = logdatetime.astimezone(timezone.utc))
                            s.sendto(buf, (dest, port))
                            packetTotal += 1
                            
                            # Ownership Report
                            buf = encoder.msgOwnershipReport(latitude=latitude, longitude=longitude, altitude=altitude+160, hVelocity=groundspeed, vVelocity=verticalspeed, trackHeading=track, misc=9, callSign=callSign)
                            s.sendto(buf, (dest, port))
                            packetTotal += 1
                            
                            # Ownership Geometric Altitude
                            buf = encoder.msgOwnershipGeometricAltitude(altitude=altitude+160)
                            s.sendto(buf, (dest, port))
                            packetTotal += 1
                            
                            # GPS Time, Custom 101 Message
                            buf = encoder.msgGpsTime(count=packetTotal, quality=1, hour=logdatetime.hour, minute=logdatetime.minute)
                            s.sendto(buf, (dest, port))
                            packetTotal += 1
                            
                            # On-screen status output 
                            if (timeSim % 10 == 0):
                                showdatetime = logdatetime + timedelta(seconds=timeSim-lastTimeSim)
                                prttext = "#%04d Real Time %s, lat=%09.5f, long=%09.5f, altitude=%05d, track=%05.1f, lasttrack=%+05.1f, nexttrack=%+05.1f, groundspeed=%05.1f" % (num_points, showdatetime.strftime('%H:%M:%S'), latitude, longitude, altitude, track, lastTrack, nextTrack, groundspeed)
                                print(prttext)
                                if logfile > 0:
                                    log_file.write(prttext + "\n")
                            timeToWait = (timeSim - startTimeSim) - (time.time()-startTimeIteration)
                            time.sleep(max(0.0, timeToWait))

                    lastLatitude = nextLatitude
                    lastLatrad = nextLatrad
                    lastLongitude = nextLongitude
                    lastLonrad = nextLonrad
                    lastAltitude = nextAltitude
                    lastTimeSim = timeSim
                    lastDir = nextTrack-lastTrack # für Drehrichtung
                    lastTrack = nextTrack
                    lastGroundspeed = nextGroundspeed
                    lastVerticalspeed = nextVerticalspeed

                    num_points = num_points + 1

                except Exception as e:
                    print(e)
                    if logfile > 0:
                        log_file.write(str(e))
                    break

    print('Sent track points of GPX-file: %d' % num_points)    
    gpx_file.close()
    if logfile > 0:
        log_file.close()
    return 0

def _options_okay(options):
    """test to see if options are valid"""
    errors = False
    dummy = None
    
    if not (options.file == "" or os.path.exists(options.file)):
        errors = True
        print_error("Argument '--file' points to non-existent file")
    if not options.start_time == '':
        try:
            dummy = time.strptime(options.start_time, time_format)
        except:
            errors = True
            print_error("Argument '--start_time' syntax is not correct")
    options.offsetStart = 0
    if not options.end_time == '':
        try:
            dummy = time.strptime(options.end_time, time_format)
        except:
            errors = True
            print_error("Argument '--send_time' syntax is not correct")
    options.duration = 18000
    
    return not errors

if __name__ == '__main__':
    
    # Get name of program from command line or else use embedded default
    progName = os.path.basename(sys.argv[0])  

    # Setup option parsing
    #
    usageMsg = "usage: %s [options]" % (progName)
    optParser = optparse.OptionParser(usage=usageMsg)

    # add options outside of any option group
    optParser.add_option("--verbose", "-v", action="store_true", help="Verbose reporting on STDERR")
    optParser.add_option("--file","-f", action="store", default="example2.gpx", type="str", metavar="FILE", help="input file (default=STDIN)")

    # optional options
    group = optparse.OptionGroup(optParser,"Optional")
    group.add_option("--callsign","-c", action="store", default="DEUKN", type="str", metavar="CALLSIGN", help="Aeroplane Callsign (default=DEUKN)")
    group.add_option("--offsetstart","-o", action="store", default="0", type="float", metavar="OFFSETSTART", help="relative time to start [s] (default=%default)")
    group.add_option("--duration","-u", action="store", default="18000", type="float", metavar="TIMEOFDURATION", help="relative duration of video [s] or absolute endtime [HH:MM:SS]) (default=%default)")
    group.add_option("--start_time","-s", action="store", default="", type="str", metavar="TIMEOFSTART", help="absolute start time [HH:MM:SS] (default=%default)") 
    group.add_option("--end_time","-e", action="store", default="", type="str", metavar="TIMEOFSTOP", help="absolute end time [HH:MM:SS] (default=%default)") 
    group.add_option("--takeoff_altitude","-t", action="store", default="-1000", type="float", metavar="TAKEOFFALT", help="Correct take off altitude [ft]) (default=%default)")
    group.add_option("--landing_altitude","-l", action="store", default="-1000", type="float", metavar="LANDINGALT", help="Correct landing altitude [ft]) (default=%default)")
    group.add_option("--dest","-d", action="store", default=DEF_SEND_ADDR, type="str", metavar="IP", help="destination IP (default=%default)")
    group.add_option("--port","-p", action="store", default=DEF_SEND_PORT, type="int", metavar="NUM", help="destination port (default=%default)")
    group.add_option("--logfile","-g", action="store", default=1, type="int", metavar="LOGFILE", help="write a log file (default=%default)")
    
    optParser.add_option_group(group)

    # do the option parsing
    (options, args) = optParser.parse_args(args=sys.argv[1:])

    # check options
    if not _options_okay(options):
        print_error("Stopping due to option errors.")
        sys.exit(EXIT_CODE['OPTIONS'])

    simulateIt(options.file, options.callsign, options.offsetstart, options.duration, options.takeoff_altitude, options.landing_altitude, 
               options.dest, options.port, options.start_time, options.end_time, options.logfile)