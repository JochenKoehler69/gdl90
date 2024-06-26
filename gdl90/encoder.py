#
# encoder.py
#

import datetime
import struct
from gdl90.fcs import crcCompute

def wait_for_key():
    while True:
        if msvcrt.kbhit():
            return msvcrt.getch()
        
class Encoder(object):
    """GDL-90 data link interface decoder class"""

    def __init__(self):
        pass
    
    
    def _addCrc(self, msg):
        """compute the CRC for msg and append CRC bytes to msg"""
        crcBytes = crcCompute(msg)
        msg.extend(crcBytes)
    
    
    def _escape(self, msg):
        """escape 0x7d and 0x7e characters"""
        msgNew = bytearray()
        escapeChar = 0x7d
        charsToEscape = (0x7d, 0x7e)
        
        for i in range(len(msg)):
            c = msg[i]
            if c in charsToEscape:
                msgNew.append(escapeChar)
                msgNew.append(c ^ 0x20)
            else:
                msgNew.append(c)
        return(msgNew)
    
    
    def _preparedMessage(self, msg):
        """returns a prepared a message with CRC, escapes it, adds begin/end markers"""
        self._addCrc(msg)
        msgNew = self._escape(msg)
        msgNew.insert(0,0x7e)
        msgNew.append(0x7e) 
        return(msgNew)
    
    
    def _pack24bit(self, num):
        """make a 24 bit packed array (MSB) from an unsigned number"""
        a = bytearray()
        a.append((num & 0xff0000) >> 16)
        a.append((num & 0x00ff00) >> 8)
        a.append(num & 0xff)
        return(a)


    def _makeLatitude(self, latitude):
        """convert a signed integer latitude to 2s complement ready for 24-bit packing"""
        if latitude > 90.0:  latitude = 90.0
        if latitude < -90.0:  latitude = -90.0
        latitude = int(latitude * (0x800000 / 180.0))
        if latitude < 0:
            latitude = (0x1000000 + latitude) & 0xffffff  # 2s complement
        return(latitude)


    def _makeLongitude(self, longitude):
        """convert a signed integer longitude to 2s complement ready for 24-bit packing"""
        if longitude > 180.0:  longitude = 180.0
        if longitude < -180.0:  longitude = -180.0
        longitude = int(longitude * (0x800000 / 180.0))
        if longitude < 0:
            longitude = (0x1000000 + longitude) & 0xffffff  # 2s complement
        return(longitude)
    
    def msgHeartbeat(self, st1=0x81, st2=0x00, ts=None):
        """message ID #0"""
        # Auto-fill timestamp if not provided
        if ts is None:
            ts = datetime.datetime.utcnow()
        
        ts = (ts.hour * 3600) + (ts.minute * 60) + ts.second
        # Move 17-bit into status byte 2 if necessary
        if (ts & 0x10000) != 0:
            ts = ts & 0x0ffff
            st2 = st2 | 0x80
     
        msg = bytearray.fromhex("00") 
        fmt = '>BBH'
        msg.extend(struct.pack(fmt,st1,st2,ts))
        msg.extend(bytearray.fromhex("00 00"))
                
        return(self._preparedMessage(msg))
    
    
    def msgOwnershipReport(self, status=0, addrType=0, address=0, latitude=0.0, longitude=0.0, altitude=0.0, misc=9, navIntegrityCat=8, navAccuracyCat=8, hVelocity=None, vVelocity=None, trackHeading=0, emitterCat=1, callSign='', code=0):
        """message ID #10"""
        return(self._msgType10and20([10], status, addrType, address, latitude, longitude, altitude, misc, navIntegrityCat, navAccuracyCat, hVelocity, vVelocity, trackHeading, emitterCat, callSign, code))
    
    
    def msgTrafficReport(self, status=0, addrType=0, address=0, latitude=0.0, longitude=0.0, altitude=0.0, misc=9, navIntegrityCat=8, navAccuracyCat=8, hVelocity=None, vVelocity=None, trackHeading=0, emitterCat=1, callSign='', code=0):
        """message ID #20"""
        return(self._msgType10and20([20], status, addrType, address, latitude, longitude, altitude, misc, navIntegrityCat, navAccuracyCat, hVelocity, vVelocity, trackHeading, emitterCat, callSign, code))
    
    
    def _msgType10and20(self, msgid, status, addrType, address, latitude, longitude, altitude, misc, navIntegrityCat, navAccuracyCat, hVelocity, vVelocity, trackHeading, emitterCat, callSign, code):
        """construct message ID 10 or 20"""
        msg = bytearray(msgid)
        
        b = ((status & 0xf) << 4) | (addrType & 0xf)
        msg.append(b)
                    
        msg.extend(self._pack24bit(address))
        msg.extend(self._pack24bit(self._makeLatitude(latitude)))
        msg.extend(self._pack24bit(self._makeLongitude(longitude)))
                    
        altitude = int((altitude + 1000) / 25)
        if altitude < 0:  altitude = 0
        if altitude > 0xffe:  altitude = 0xffe
        
        # altitude is bits 15-4, misc code is bits 3-0
        msg.append((altitude & 0xff0) >> 4)  # top 8 bits of altitude
        msg.append( ((altitude & 0xf) << 4) | (misc & 0xf) )
        
        # nav int cat is top 4 bits, acc cat is bottom 4 bits
        msg.append( ((navIntegrityCat & 0xf) << 4) | (navAccuracyCat & 0xf) )
        
        if hVelocity is None:
            hVelocity = 0xfff
        elif hVelocity < 0:
            hVelocity = 0
        elif hVelocity > 0xffe:
            hVelocity = 0xffe
        else:
            hVelocity = int(hVelocity)
        if vVelocity is None:
            vVelocity = 0x800
        else:
            if vVelocity > 32576:
                vVelocity = 0x1fe
            elif vVelocity < -32576:
                vVelocity = 0xe02
            else:
                vVelocity = int(vVelocity / 64)  # convert to 64fpm increments
                if vVelocity < 0:
                    vVelocity = (0x1000000 + vVelocity) & 0xffffff # 2s complement
        
        # packing hVelocity, vVelocity into 3 bytes:  hh hv vv
        msg.append((hVelocity & 0xff0) >> 4)
        msg.append( ((hVelocity & 0xf) << 4) | ((vVelocity & 0xf00) >> 8) )
        msg.append(vVelocity & 0xff)
        trackHeading = int(trackHeading / (360. / 256)) # convert to 1.4 deg single byte        
        msg.append(int(trackHeading) & 0xff)
        
        msg.append(emitterCat & 0xff)
        
        callSign = (callSign + " "*8)[:8]
        msg.extend(map(ord, callSign))
        
        # code is top 4 bits, bottom 4 bits are 'spare'
        msg.append((code & 0xf) << 4)
            
        return(self._preparedMessage(msg))
    
    
    def msgOwnershipGeometricAltitude(self, altitude=0, merit=50, warning=False):
        """message ID #11"""
        msg = bytearray.fromhex("0b")
        
        # Convert altitude to 5ft increments
        altitude = int(altitude / 5)
        if altitude < 0:
            altitude = (0x10000 + altitude) & 0xffff  # 2s complement
        msg.extend(struct.pack('>H', altitude))  # 16-bit big endian
        
        if merit is None:
            merit = 0x7fff
        elif merit > 32766:
            merit = 0x7ffe
        
        # MSB is warning bit, 6-0 bits are MSB of merit value
        b = (merit & 0x7f00) >> 8  # top 7 bits of merit value
        if warning:
            b = b | 0x80  # set MSB to 1
        msg.append(b)
        msg.append(merit & 0xff)  # bottom 8 bits of merit value
        
        return(self._preparedMessage(msg))
    
    
    def msgGpsTime(self, count=0, quality=2, hour=None, minute=None):
        """message ID #101 for Skyradar"""
        msg = bytearray.fromhex("65 2a 00")
        
        msg.append((0x30 + quality) & 0xff)  # GPS quality: '0'=no fix, '1'=regular, '2'=DGPS (WAAS)
            
        msg.extend(struct.pack('<I',count)[:-1])  # use first three LSB bytes only
        
        if hour is None or minute is None:
             # Auto-fill timestamp if not provided
                dt = datetime.datetime.utcnow()
                hour = dt.hour
                minute = dt.minute
        msg.append(hour & 0xff)
        msg.append(minute & 0xff)
        
        msg.append(0); msg.append(0)  # debug data
        msg.append(4) # hardware version     

        return(self._preparedMessage(msg))
    
    
    def msgStratuxHeartbeat(self, st1=0x02, ver=1):
        """message ID #204 for Stratux heartbeat"""
        msg = bytearray(b'0xcc')
        fmt = '>B'
        data = st1 & 0x03  # lower two bits only
        data += ((ver & 0x3f) << 2)  # lower 6 bits of version packed into upper 6 of data
        msg.extend(struct.pack(fmt,data))
        
        return(self._preparedMessage(msg))
    
    
    def msgSXHeartbeat(self, fv=0x0011, hv=0x0001, st1=0x02, st2=0x01, satLock=0, satConn=0, num978=0, num1090=0, rate978=0, rate1090=0, cpuTemp=0, towers=[]):
        """message ID #29 for Hiltonsoftware SX heartbeat"""
        
        msg = bytearray(b'0x1d')
        fmt = '>HHBBLLHHBBHHHHHB'
        msg.extend(struct.pack(fmt,ord('S'),ord('X'),1,1,fv,hv,st1,st2,satLock,satConn,num978,num1090,rate978,rate1090,cpuTemp,len(towers)))

        for tower in towers:
            (lat, lon) = tower[0:2]
            msg.extend(self._pack24bit(self._makeLatitude(lat)))
            msg.extend(self._pack24bit(self._makeLongitude(lon)))
        
        return(self._preparedMessage(msg))


    def msgForeFlightMessage101(self, subId=0, mv=1, sn=None, nameShort="Stratux", nameLong="gdl90-encoder", capmask=1):
        """message ID #101 for ForeFlight"""
        
        if sn is None:
            sn = 0xff*8
        else:
            sn = str(sn + " "*8)[:8]
        nameShort = str(nameShort + " "*8)[:8]
        nameLong = str(nameLong + " "*16)[:16]

        msg = bytearray(b'0x65')
        fmt = '>BB8s8s16sB'
        msg.extend(struct.pack(fmt, subId, mv, sn, nameShort, nameLong, capmask))

        return(self._preparedMessage(msg))
