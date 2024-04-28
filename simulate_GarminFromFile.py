#!/usr/bin/env python
#
# simulate_GarminFromFile.py
#


import time
from datetime import datetime, timezone, timedelta
import socket
import gdl90.encoder
import os
import sys
import optparse
import csv
from pygame import mixer
from collections import namedtuple

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

# These are the identifiers in a Garmin CSV file G1000
class cvsIDs(namedtuple('IDs_G1000', ['id_Callsign', 'id_date', 'id_UTCOffset', 'id_time', 'id_latitude', 'id_longitude', 
                                      'id_altitudeMSL', 'id_altitudeGPS', 'id_altitudeP', 'id_heading', 'id_track', 'id_groundspeed', 'id_airspeed', 
                                      'id_trueairspeed', 'id_verticalspeed', 'id_windspeed', 'id_winddir'])):
    pass

G1000_IDs = cvsIDs(id_Callsign='aircraft_ident=', id_date='Lcl Date', id_UTCOffset='UTCOfst', id_time='Lcl Time', id_latitude='Latitude', 
                   id_longitude='Longitude', id_altitudeMSL='AltMSL', id_altitudeGPS='AltGPS', id_altitudeP='AltP', id_heading='HDG', id_track='TRK', 
                   id_groundspeed='GndSpd', id_airspeed='IAS', id_trueairspeed='TAS', id_verticalspeed='VSpdG', id_windspeed='WndSpd', id_winddir='WndDr')

# Date (yyyy-mm-dd),Time (hh:mm:ss),UTC Time (hh:mm:ss),UTC Offset (hh:mm),Latitude (deg),Longitude (deg),GPS Altitude (ft),GPS Fix Status,GPS Time of Week (sec),GPS Ground Speed (kt),GPS Ground Track (deg),GPS Velocity E (m/sec),GPS Velocity N (m/sec),GPS Velocity U (m/sec),Magnetic Heading (deg),GPS PDOP,GPS Sats,Pressure Altitude (ft),Baro Altitude (ft),Vertical Speed (ft/min),Indicated Airspeed (kt),True Airspeed (kt),Pitch (deg),Roll (deg),Lateral Acceleration (G),Normal Acceleration (G),AOA Cp,AOA,Selected Heading (deg),Selected Altitude (ft),Selected Vertical Speed (ft/min),Selected Airspeed (kt),Baro Setting (inch Hg),COM Frequency (MHz),NAV Frequency (MHz),Active Nav Source,Nav Annunciation,Nav Identifier,Nav Distance (nm),Nav Bearing (deg),Nav Course (deg),Nav Cross Track Distance (nm),Horizontal CDI Deflection,Horizontal CDI Full Scale (ft),Horizontal CDI Scale,Vertical CDI Deflection,Vertical CDI Full Scale (ft),VNAV CDI Deflection,VNAV Altitude (ft),Autopilot State,FD Lateral Mode,FD Vertical Mode,FD Roll Command (deg),FD Pitch Command (deg),FD Altitude (ft),AP Roll Command (deg),AP Pitch Command (deg),AP VS Command (ft/min),AP Altitude Command (ft),AP Roll Torque (%),AP Pitch Torque (%),AP Roll Trim Motor,AP Pitch Trim Motor,Magnetic Variation (deg),Outside Air Temp (deg C),Density Altitude (ft),Height Above Ground (ft),Wind Speed (kt),Wind Direction (deg),AHRS Status,AHRS Dev (%),Magnetometer Status,Network Status,Transponder Code,Transponder Mode,Oil Temp (deg F),Fuel L Qty (gal),Fuel R Qty (gal),Fuel Press (PSI),Oil Press (PSI),RPM,   Manifold Press (inch Hg),Volts 1,Volts E,Amps, Fuel Flow (gal/hour),Co Ppm,CHT1 (deg F),CHT2 (deg F),EGT1 (deg F),EGT2 (deg F),ALT2 (discrete),ALT1 (discrete),BACKUP BATT  (discrete),CAS Alert,Terrain Alert,Engine 1 Cycle Count
# Lcl Date,         Lcl Time,       UTC Time,           UTCOfst,           Latitude,      Longitude,      AltGPS,           GPSfix,                              ,GndSpd,               TRK,                   GPSVelE,               GPSVelN,               GPSVelU,               HDG,                   PDOP,            ,AltP,                  AltInd,            VSpd,                   IAS,                    TAS,               Pitch,      Roll,      LatAc,                   NormAc,                       ,AOA,SelHDG,                SelALT,                SelVSpd,                         SelIAS,                Baro,                  COM1,               NAV1,               NavSrc,          ,                 NavIdent,      NavDist,          NavBrg,           NavCRS,          NavXTK,                       HCDI,                    ,                              ,                                             VCDI,                       ,VNAV CDI,           VNAVAlt,                          ,               ,                ,                     ,                      ,                ,                     ,                      ,                      ,                        ,                  ,                   ,                  ,                   ,MagVar,                  OAT,                     AltD,                 AGL,                     WndSpd,         WndDr,                                       ,                   ,              ,                ,               ,,E1 OilT,         FQty1,           FQty2,           E1 FPres,        E1 OilP,        E1 RPM,E1 MAP,                  Volts1, Volts2, Amps1,E1 FFlow,                  ,E1 CHT1,     E1 CHT2,     E1 EGT1,     E1 EGT2,                    ,,,,,

GDU460_IDs = cvsIDs(id_Callsign='aircraft_ident=', id_date='Lcl Date', id_UTCOffset='UTCOfst', id_time='Lcl Time', id_latitude='Latitude', 
                    id_longitude='Longitude', id_altitudeMSL='AltInd', id_altitudeGPS='AltGPS', id_altitudeP='AltP', id_heading='HDG', id_track='TRK', 
                    id_groundspeed='GndSpd', id_airspeed='IAS', id_trueairspeed='TAS', id_verticalspeed='VSpd', id_windspeed='WndSpd', id_winddir='WndDr')

# Date-Format
datetime_format = '%Y-%m-%d %H:%M:%S %z'
time_format = '%H:%M:%S'
opt_starttime = None
opt_endtime = None

# Exit codes
EXIT_CODE = {
    "OK" : 0,
    "OPTIONS" : 1,
    "OTHER" : 99,
}
   
def print_error(msg):
    """print an error message"""
    print(sys.stderr, msg)

def simulateIt(filename, callSign='', offsetstart=0, duration=18000, takeoff_altitude=-2000.0, landing_altitude=-2000.0, dest="255.255.255.255", port=43211, starttimeStr='', endtimeStr=''):
    print("Simulating Skyradar from Garmin CSV File")
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
    OffsetLandingAltitudeMSL = 0
    OffsetTakeOffAltitudeMSL = 0
    gradOffsetAltitudeMSL = 0
    OffsetLandingAltitudeP = 0
    OffsetTakeOffAltitudeP = 0
    gradOffsetAltitudeP = 0
    TakeOffDetectedForOffset = False

    # First look for the correct call sign and on what line to start the csv reader
    with open(filename, 'r') as csv_file:
        # read all lines using readline()
        lines = csv_file.readlines()
        posStartofCSV = 0
        posStartofValues = 0
        lenLastLine = 0
        ProductName = ''
        callSign = ''
        for line in lines:
            posStartofCSV = posStartofCSV + lenLastLine
            lenLastLine = len(line)
            listofValues = line.split(",")
            for value in listofValues:
                if ProductName == '':
                    startID = value.find('product=') 
                    if startID >= 0:
                        ProductName = value[startID+len('product=')+1:len(value)-1]
                        if ProductName == "GDU 460":
                            Product_IDs = GDU460_IDs
                        else:
                            Product_IDs = G1000_IDs
                    else:
                        continue
                if callSign == '':
                    startID = value.find(Product_IDs.id_Callsign) 
                    if startID >= 0:
                        callSign = value[startID+len(Product_IDs.id_Callsign)+1:len(value)-1]
                        break
            if line.find(Product_IDs.id_date) >= 0:
                posStartofValues = posStartofCSV + lenLastLine
                break
        # Now we are at the start of the csv-file
        csv_file.seek(posStartofCSV)
        reader = csv.DictReader(csv_file)
        # First run to detect take-off and landing
        for row in reader:
            groundspeed = float(row[Product_IDs.id_groundspeed])
            verticalspeed = float(row[Product_IDs.id_verticalspeed])
            airspeed = float(row[Product_IDs.id_airspeed])            
            currdatetime_str = row[Product_IDs.id_date] + ' ' + row[Product_IDs.id_time] + ' ' + row[Product_IDs.id_UTCOffset].replace(":", "")
            currdatetime = datetime.strptime(currdatetime_str, datetime_format)
            if groundspeed > 40 and airspeed > 40 and verticalspeed > 100:
                if not TakeOffDetectedForOffset:
                    if takeoff_altitude > -1000.0 and landing_altitude > - 1000.0:
                        OffsetTakeOffAltitudeGPS = takeoff_altitude - float(row[Product_IDs.id_altitudeGPS])+30
                        OffsetTakeOffAltitudeMSL = takeoff_altitude - float(row[Product_IDs.id_altitudeMSL])+30
                        OffsetTakeOffAltitudeP = takeoff_altitude - float(row[Product_IDs.id_altitudeP])+30
                    TakeOffTime = currdatetime
                    print("Takeoff at %s with altitude offset: %d" % (TakeOffTime.strftime('%H:%M:%S'), OffsetTakeOffAltitudeGPS))
                    TakeOffDetectedForOffset = True
            else:
                if not TakeOffDetectedForOffset: 
                    continue
                if TakeOffDetectedForOffset and groundspeed < 30 and airspeed > 30 and abs(verticalspeed) < 100:
                    LandingTime = currdatetime
                    if takeoff_altitude > -1000.0 and landing_altitude > - 1000.0:
                        OffsetLandingAltitudeGPS = landing_altitude - float(row[Product_IDs.id_altitudeGPS])
                        OffsetLandingAltitudeMSL = landing_altitude - float(row[Product_IDs.id_altitudeMSL])
                        OffsetLandingAltitudeP = landing_altitude - float(row[Product_IDs.id_altitudeP])
                        gradOffsetAltitudeGPS = (OffsetLandingAltitudeGPS - OffsetTakeOffAltitudeGPS) / (LandingTime - TakeOffTime).total_seconds()
                        gradOffsetAltitudeMSL = (OffsetLandingAltitudeMSL - OffsetTakeOffAltitudeMSL) / (LandingTime - TakeOffTime).total_seconds()
                        gradOffsetAltitudeP = (OffsetLandingAltitudeP - OffsetTakeOffAltitudeP) / (LandingTime - TakeOffTime).total_seconds()
                    print("Landing at %s with altitude offset: %d" % (LandingTime.strftime('%H:%M:%S'), OffsetLandingAltitudeGPS))
                    break


        # This is the second run
        csv_file.seek(posStartofValues)
        startTimeIteration = time.time()
        for row in reader:
            try:
                timeStart = time.time()  # mark start time - just for delay
                currdatetime_str = row[Product_IDs.id_date] + ' ' + row[Product_IDs.id_time] + ' ' + row[Product_IDs.id_UTCOffset].replace(":", "")
                currdatetime = datetime.strptime(currdatetime_str, datetime_format)
                timeSim = currdatetime.second + currdatetime.minute *60 + currdatetime.hour *3600
                # Altitude correction
                if TakeOffDetectedForOffset:
                    OffsetAltitudeGPS = OffsetTakeOffAltitudeGPS + gradOffsetAltitudeGPS * max(0.0, (min(currdatetime, LandingTime) - TakeOffTime).total_seconds())
                    OffsetAltitudeMSL = OffsetTakeOffAltitudeMSL + gradOffsetAltitudeMSL * max(0.0, (min(currdatetime, LandingTime) - TakeOffTime).total_seconds())
                    OffsetAltitudeP = OffsetTakeOffAltitudeP + gradOffsetAltitudeP * max(0.0, (min(currdatetime, LandingTime) - TakeOffTime).total_seconds())
                else:
                    OffsetAltitudeGPS = 0
                    OffsetAltitudeMSL = 0
                    OffsetAltitudeP = 0
                if FirstIt:
                    FirstIt = False
                    startTimeSim = timeSim
                    if StartTime is None:
                        StartTime = currdatetime + timedelta(offsetstart)
                    else:
                        # Zeit auf Datum draufrechnen
                        StartTime = datetime.combine(currdatetime.date(), StartTime)
                    if EndTime is None:
                        EndTime = currdatetime + timedelta(offsetstart) + timedelta(duration)
                    else:
                        # Zeit auf Datum draufechnen
                        EndTime = datetime.combine(currdatetime.date(), EndTime)
                if currdatetime < StartTime: # did we pass start time already?
                    startTimeSim = timeSim
                    continue
                elif currdatetime > EndTime: # is duration over already? 
                    break

                altitudeMSL = float(row[Product_IDs.id_altitudeMSL]) + OffsetAltitudeMSL
                altitudeGPS = float(row[Product_IDs.id_altitudeGPS]) + OffsetAltitudeGPS
                altitudeP = float(row[Product_IDs.id_altitudeP]) + OffsetAltitudeP
                groundspeed = float(row[Product_IDs.id_groundspeed])
                verticalspeed = float(row[Product_IDs.id_verticalspeed])
                latitude = float(row[Product_IDs.id_latitude])
                longitude = float(row[Product_IDs.id_longitude])
                heading = float(row[Product_IDs.id_heading])
                if row[Product_IDs.id_track]=='':
                    track = heading
                else:
                    track = float(row[Product_IDs.id_track])
                airspeed = float(row[Product_IDs.id_airspeed])
            except Exception as e:
                print(e)
                break
            
            # Heartbeat Message
            buf = encoder.msgHeartbeat(ts = currdatetime.astimezone(timezone.utc))
            s.sendto(buf, (dest, port))
            packetTotal += 1
            
            # Ownership Report
            buf = encoder.msgOwnershipReport(latitude=latitude, longitude=longitude, altitude=altitudeP, hVelocity=groundspeed, vVelocity=verticalspeed, trackHeading=track, misc=9, callSign=callSign)
            s.sendto(buf, (dest, port))
            packetTotal += 1
            
            # Ownership Geometric Altitude
            buf = encoder.msgOwnershipGeometricAltitude(altitude=altitudeGPS+100)
            s.sendto(buf, (dest, port))
            packetTotal += 1
            
            # GPS Time, Custom 101 Message
            buf = encoder.msgGpsTime(count=packetTotal, quality=1, hour=currdatetime.hour, minute=currdatetime.minute)
            s.sendto(buf, (dest, port))
            packetTotal += 1
            
            # On-screen status output 
            if (currdatetime.second % 10 == 0):
                print("Real Time %s, lat=%3.6f, long=%3.6f, altitudeGPS=%d, heading=%d, groundspeed=%d, airspeed=%d" % (currdatetime.strftime('%H:%M:%S'), latitude, longitude, altitudeGPS, heading, groundspeed, airspeed))
                
            # Delay for the rest of this second
            timeToWait = (timeSim - startTimeSim) - (time.time()-startTimeIteration)
            time.sleep(max(0.0, timeToWait))

    print('Sent lines of csv-file: %d' % (reader.line_num))    
    csv_file.close()

    #playing the sound
    # plays.play()
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
    optParser.add_option("--file","-f", action="store", default="example-g3x.csv", type="str", metavar="FILE", help="input file (default=STDIN)")

    # optional options
    group = optparse.OptionGroup(optParser,"Optional")
    group.add_option("--callsign","-c", action="store", default="DEUKN", type="str", metavar="CALLSIGN", help="Aeroplane Callsign (default=DEUKN)")
    group.add_option("--offsetstart","-o", action="store", default="0", type="float", metavar="OFFSETSTART", help="relative time to start [s] (default=%default)")
    group.add_option("--duration","-u", action="store", default="18000", type="float", metavar="TIMEOFDURATION", help="relative duration of video [s] or absolute endtime [HH:MM:SS]) (default=%default)")
    group.add_option("--start_time","-s", action="store", default="09:45:00", type="str", metavar="TIMEOFSTART", help="absolute start time [HH:MM:SS] (default=%default)") 
    group.add_option("--end_time","-e", action="store", default="11:45:00", type="str", metavar="TIMEOFSTOP", help="absolute end time [HH:MM:SS] (default=%default)") 
    group.add_option("--takeoff_altitude","-t", action="store", default="-1000", type="float", metavar="TAKEOFFALT", help="Correct take off altitude [ft]) (default=%default)")
    group.add_option("--landing_altitude","-l", action="store", default="-1000", type="float", metavar="LANDINGALT", help="Correct landing altitude [ft]) (default=%default)")
    group.add_option("--dest","-d", action="store", default=DEF_SEND_ADDR, type="str", metavar="IP", help="destination IP (default=%default)")
    group.add_option("--port","-p", action="store", default=DEF_SEND_PORT, type="int", metavar="NUM", help="destination port (default=%default)")
    optParser.add_option_group(group)

    # do the option parsing
    (options, args) = optParser.parse_args(args=sys.argv[1:])

    # check options
    if not _options_okay(options):
        print_error("Stopping due to option errors.")
        sys.exit(EXIT_CODE['OPTIONS'])

    simulateIt(options.file, options.callsign, options.offsetstart, options.duration, options.takeoff_altitude, options.landing_altitude, 
               options.dest, options.port, options.start_time, options.end_time)