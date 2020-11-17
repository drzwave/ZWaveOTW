''' Z-Wave Over-The-Wire firmware update

    This Python program will attempt to update the firmware on a 500 series Z-Wave chip with the desired hex file.
    Note that the target MUST be OTW capable which means the interface MUST have a 2Mbit
    serial flash chip. Most UZBs do NOT have OTW capability and cannot be updated with 
    this program. Use the PC Programmer to update UZBs.
    The library type of the firmware can be changed. 
    Switching from a Static Controller to the Bridge Controller is needed to switch to Z/IP.

    This program is a DEMO only and is provided AS-IS and without support. 
    But feel free to copy and improve!
    This program can be used as a guide to implement you own firmware update in your
    language of choice.

    Usage: python ZWaveOTW.py [filename] [COMx]
    filename is the .HEX file of the firmware to be sent to the Z-Wave chip.
      If filename is not provided then the current version of the Z-Wave chip is printed.
    COMx is optional and is the COM port or /dev/tty* port of the Z-Wave interface.
    Updated to python 3 but might still be some leftover python2 oddities.

    Only 500 series Z-Wave chips have OTW. 300 series do not nor do the 400 series. The 700 series uses an entirely different method.
    However the information utilities are handy for all SerialAPI versions.

    The program has been tested and works on a Raspberry Pi with an EZZee Z-Wave interface 
    board plugged into the 40 pin header. Note that the RPi must have the UART swapped 
    with the BLE interface. The following lines must be in /boot/config.txt:
    #swap the UART so the good one goes to the GPIOs instead of the Bluetooth chip.
    enable_uart=1
    dtoverlay=pi3-miniuart-bt

   Resources:
   OTW reference material: https://www.silabs.com/community/wireless/z-wave/knowledge-base.entry.html/2018/12/19/gateway_z-wave_500-gSQb
   INS13954 - Z-Wave 500 Application Programmers Guide - https://www.silabs.com/documents/login/user-guides/INS13954-Instruction-Z-Wave-500-Series-Appl-Programmers-Guide-v6_81_0x.pdf
   SerialAPI: https://www.silabs.com/documents/login/user-guides/INS12350-Serial-API-Host-Appl.-Prg.-Guide.pdf (or search "SerialAPI" on the silabs site)
'''

import serial           # serial port control
from intelhex import IntelHex   # utilities for reading in the hex file - "pip install intelhex" if you don't already have it
import sys
import time
import os
from struct            import * # PACK


#COMPORT       = "/dev/ttyAMA0" # Serial port default - typically /dev/ttyACM0 on Linux
COMPORT       = "COM13" # Serial port default - On Windows it will be via a COMxx port

VERSION       = "1.4 - 11/17/2020"       # Version of this python program
DEBUG         = 5     # [0-10] higher values print out more debugging info - 0=off

# Handy defines mostly copied from ZW_transport_api.py
FUNC_ID_SERIAL_API_GET_INIT_DATA    = b'\x02'
FUNC_ID_SERIAL_API_APPL_NODE_INFORMATION = b'\x03'
FUNC_ID_SERIAL_API_GET_CAPABILITIES = b'\x07'
FUNC_ID_SERIAL_API_SOFT_RESET       = b'\x08'
FUNC_ID_ZW_GET_PROTOCOL_VERSION     = b'\x09'
FUNC_ID_SERIAL_API_STARTED          = b'\x0A'
FUNC_ID_ZW_SET_RF_RECEIVE_MODE      = b'\x10'
FUNC_ID_ZW_SEND_DATA                = b'\x13'
FUNC_ID_ZW_GET_VERSION              = b'\x15'
FUNC_ID_ZW_ADD_NODE_TO_NETWORK      = b'\x4A'
FUNC_ID_ZW_REMOVE_NODE_FROM_NETWORK = b'\x4B'
FUNC_ID_ZW_FIRMWARE_UPDATE_NVM      = b'\x78'

# Firmware Update NVM commands
FIRMWARE_UPDATE_NVM_INIT            = b'\x00'
FIRMWARE_UPDATE_NVM_SET_NEW_IMAGE   = b'\x01'
FIRMWARE_UPDATE_NVM_GET_NEW_IMAGE   = b'\x02'
FIRMWARE_UPDATE_NVM_UPDATE_CRC16    = b'\x03'
FIRMWARE_UPDATE_NVM_IS_VALID_CRC16  = b'\x04'
FIRMWARE_UPDATE_NVM_WRITE           = b'\x05'

# Z-Wave Library Types
ZW_LIB_CONTROLLER_STATIC  = 0x01
ZW_LIB_CONTROLLER         = 0x02
ZW_LIB_SLAVE_ENHANCED     = 0x03
ZW_LIB_SLAVE              = 0x04
ZW_LIB_INSTALLER          = 0x05
ZW_LIB_SLAVE_ROUTING      = 0x06
ZW_LIB_CONTROLLER_BRIDGE  = 0x07
ZW_LIB_DUT                = 0x08
ZW_LIB_ZERONINE           = 0x09
ZW_LIB_AVREMOTE           = 0x0A
ZW_LIB_AVDEVICE           = 0x0B
libType = {
ZW_LIB_CONTROLLER_STATIC  : "Static Controller",
ZW_LIB_CONTROLLER         : "Controller",
ZW_LIB_SLAVE_ENHANCED     : "Slave Enhanced",
ZW_LIB_SLAVE              : "Slave",
ZW_LIB_INSTALLER          : "Installer",
ZW_LIB_SLAVE_ROUTING      : "Slave Routing",
ZW_LIB_CONTROLLER_BRIDGE  : "Bridge Controller",
ZW_LIB_DUT                : "DUT",
ZW_LIB_ZERONINE           : "UNKNOWN",
ZW_LIB_AVREMOTE           : "AVREMOTE",
ZW_LIB_AVDEVICE           : "AVDEVICE" }

ADD_NODE_ANY       =         b'\x01'
ADD_NODE_CONTROLLER=         b'\x02'
ADD_NODE_SLAVE     =         b'\x03'
ADD_NODE_EXISTING  =         b'\x04'
ADD_NODE_STOP      =         b'\x05'
ADD_NODE_SMART_START =       b'\x09'
TRANSMIT_COMPLETE_OK      =  b'\x00'
TRANSMIT_COMPLETE_NO_ACK  =  b'\x01'
TRANSMIT_COMPLETE_FAIL    =  b'\x02'
TRANSMIT_ROUTING_NOT_IDLE =  b'\x03'
TRANSMIT_OPTION_ACK =        b'\x01'
TRANSMIT_OPTION_AUTO_ROUTE = b'\x04'
TRANSMIT_OPTION_EXPLORE =    b'\x20'
# SerialAPI defines
SOF = b'\x01'
ACK = b'\x06'
NAK = b'\x15'
CAN = b'\x18'
REQUEST  = b'\x00'
RESPONSE = b'\x01'
# Most Z-Wave commands want the autoroute option on to be sure it gets thru. Don't use Explorer though as that causes unnecessary delays.
TXOPTS = bytes([TRANSMIT_OPTION_AUTO_ROUTE[0] | TRANSMIT_OPTION_ACK[0]])

# See INS13954-12 section 7 Application Note: Z-Wave Protocol Versions on page 433
ZWAVE_VER_DECODE = {# Z-Wave version to SDK decoder: https://www.silabs.com/products/development-tools/software/z-wave/embedded-sdk/previous-versions
        b"6.09" : "SDK 6.82.01 04/2020",
        b"6.08" : "SDK 6.82.00 Beta   ",
        b"6.07" : "SDK 6.81.06 07/2019",
        b"6.06" : "SDK 6.81.05        ",
        b"6.05" : "SDK 6.81.04        ",
        b"6.04" : "SDK 6.81.03 01/2019",
        b"6.03" : "SDK 6.81.02        ",
        b"6.02" : "SDK 6.81.01 10/2018",
        b"6.01" : "SDK 6.81.00 09/2018",
        b"5.03" : "SDK 6.71.03        ",
        b"5.02" : "SDK 6.71.02 07/2017",
        b"4.61" : "SDK 6.71.01 03/2017",
        b"4.60" : "SDK 6.71.00 01/2017",
        b"4.62" : "SDK 6.61.01 04/2017",  # This is the INTERMEDIATE version?
        b"4.33" : "SDK 6.61.00 04/2016",
        b"4.54" : "SDK 6.51.10 02/2017",
        b"4.38" : "SDK 6.51.09 07/2016",
        b"4.34" : "SDK 6.51.08 05/2016",
        b"4.24" : "SDK 6.51.07 02/2016",
        b"4.05" : "SDK 6.51.06 06/2015 or SDK 6.51.05 12/2014",
        b"4.01" : "SDK 6.51.04 05/2014",
        b"3.99" : "SDK 6.51.03 07/2014",
        b"3.95" : "SDK 6.51.02 05/2014",
        b"3.92" : "SDK 6.51.01 04/2014",
        b"3.83" : "SDK 6.51.00 12/2013",
        b"3.79" : "SDK 6.50.01        ",
        b"3.71" : "SDK 6.50.00        ",
        b"3.35" : "SDK 6.10.00        ",
        b"3.41" : "SDK 6.02.00        ",
        b"3.37" : "SDK 6.01.03        "
        }

class ZWaveOTW():
    ''' Z-Wave controller Over-The-Wire Firmware Update '''
    def __init__(self):         # parse the command line arguments and open the serial port
        self.COMPORT=COMPORT
        self.filename=""
        if len(sys.argv)==1:     # No arguments then just print the status if the serial port can be opened
            pass
        elif len(sys.argv)==2: 
            if "COM" in sys.argv[1] or "tty" in sys.argv[1]: # no filename - just check the status
                self.COMPORT=sys.argv[1]
            else:                                           # use the default COMPORT
                self.filename=sys.argv[1]
        elif len(sys.argv)==3:                           # Both comport and filename
            if "COM" in sys.argv[2] or "tty" in sys.argv[2]:
                self.COMPORT=sys.argv[2]
                self.filename=sys.argv[1]
            elif "COM" in sys.argv[1] or "tty" in sys.argv[1]:
                self.COMPORT=sys.argv[1]
                self.filename=sys.argv[2]
        else:
            self.usage()
            sys.exit()
        if DEBUG>3: print("COM Port set to {}".format(self.COMPORT))
        if DEBUG>3: print("Filename set to {}".format(self.filename))
        try:
            self.UZB= serial.Serial(port=self.COMPORT,baudrate=115200,timeout=2)
        except serial.SerialException:
            print("Unable to open serial port {}".format(self.COMPORT))
            raise

    def checksum(self,pkt):
        ''' compute the Z-Wave SerialAPI checksum at the end of each frame'''
        s=0xff
        for c in pkt:
            s ^= c
        return bytes([s])

    def GetRxChar( self, timeout=100):
        ''' Get a character from the UART or timeout in 100ms'''
        while timeout >0 and not self.UZB.in_waiting:
            time.sleep(0.001)
            timeout -=1
        if timeout>0:
            retval= self.UZB.read()
        else:
            retval= None
            print("got nothing")
        return retval

    def GetZWave( self, timeout=5000):
        ''' Receive a frame from the UART and return the binary string or timeout in TIMEOUT ms and return None'''
        pkt=b''
        c=self.GetRxChar(timeout)
        if c == None:
            if DEBUG>1: print("GetZWave Timeout!")
            return None
        while c!=SOF:   # get synced on the SOF
            if DEBUG>5: print("SerialAPI Not SYNCed {:02X}".format(ord(c)))
            c=self.GetRxChar(timeout)
        if c!=SOF:
            return None
        length=self.GetRxChar()[0]
        for i in range(length):
            c=self.GetRxChar()
            pkt += c
        checksum= self.checksum(pkt)[0]
        checksum ^= length  # checksum includes the length
        if checksum!=0:
            if DEBUG>1: print("GetZWave checksum failed {:02x}".format(checksum))
        self.UZB.write(ACK)  # ACK the returned frame - we don't send anything else even if the checksum is wrong
        return pkt[1:-1] # strip off the type and checksum
 
 
    def Send2ZWave( self, SerialAPIcmd, returnStringFlag=False, timeout=5000):
        ''' Send the command via the SerialAPI to the Z-Wave chip and optionally wait for a response.
            If ReturnStringFlag=True then returns a binary string of the SerialAPI frame response within TIMEOUT ms
            else returns None
            Waits 100ms for the ACK/NAK/CAN for the SerialAPI and strips that off. 
            Removes all SerialAPI data from the UART before sending and ACKs to clear any retries.
        '''
        time.sleep(.1)
        if self.UZB.in_waiting: 
            self.UZB.write(ACK)  # ACK just to clear out any retries
            if DEBUG>5: print("Dumping ", end='')
        while self.UZB.in_waiting: # purge UART RX to remove any old frames we don't want
            c=self.UZB.read()
            if DEBUG>5: print("{:02X}".format(c), end='', flush=True)
        frame = bytes([len(SerialAPIcmd)+2]) + REQUEST + SerialAPIcmd # add LEN and REQ bytes which are part of the checksum
        chksum= self.checksum(frame)
        pkt = SOF + frame + chksum # add SOF to front and CHECKSUM to end
        if DEBUG>8: print("pkt={}".format(pkt))
        for retries in range(1,4):                        # retry up to 3 times. Z-Wave traffic often causes the UART to lose the SOF and drop the frame.
            self.UZB.write(pkt)  # send the command
            #if DEBUG>9: print("Sending ", end='')
            #for c in pkt:
            #    if DEBUG>9: print("{:02X},".format(c), end='', flush=True)
            #    self.UZB.write(c)  # send the command
            #if DEBUG>9: print(" ")
            # should always get an ACK/NAK/CAN so wait for it here
            c=self.GetRxChar(500) # wait for the ACK
            if c==None:
                if DEBUG>1: print("no ACK on try #{}".format(retries),flush=True)
                for i in range(32):
                    self.UZB.write(ACK)       # send ACKs to see if the LEN was incorrectly received 
                    if self.UZB.inWaiting(): break      # if we get an ACK/NAK/CAN then stop sending ACKs and retry
            elif c==ACK:                       # then the frame is OK so no need to retry
                break
            elif c!=ACK:                       # didn't expect this so just retry
                if DEBUG>1: print("Error - not ACKed = 0x{:02X}".format(c))
                self.UZB.write(ACK)                 # send an ACK to try clear out whatever the problem might be
                while self.UZB.in_waiting:         # purge UART RX to remove any old frames we don't want
                    c=self.UZB.read()
        if retries>1 and DEBUG>5:
            print("Took {} tries".format(retries))
        response=None
        if returnStringFlag:    # wait for the returning frame for up to 5 seconds
            response=self.GetZWave(timeout)    
        return response
            

    def RemoveLifeline( self, NodeID):
        ''' Remove the Lifeline Association from the NodeID (integer). 
            Helps eliminate interfering traffic being sent to the controller during the middle of range testing.
        '''
        pkt=self.Send2ZWave(pack("!9B",FUNC_ID_ZW_SEND_DATA, NodeID, 4, 0x85, 0x04, 0x01, 0x01, TXOPTS, 78),True)
        pkt=self.GetZWave(10*1000)
        if pkt==None or ord(pkt[2])!=0:
            if DEBUG>1: print("Failed to remove Lifeline")
        else:
            print("Lifeline removed")
        if DEBUG>10: 
            for i in range(len(pkt)): 
                print("{:02X}".format(ord(pkt[i])),end='')

    def PrintVersion(self):
        pkt=self.Send2ZWave(FUNC_ID_SERIAL_API_GET_CAPABILITIES,True)
        if pkt==None:
            print("Unable to get SerialAPI capabilities - exiting")
            exit()
        (ver, rev, man_id, man_prod_type, man_prod_type_id, supported) = unpack("!2B3H32s", pkt[1:])
        print("SerialAPI Ver={0}.{1}".format(ver,rev))   # SerialAPI version is different than the SDK version
        print("Mfg={:04X}".format(man_id),end='')
        if man_id==0: 
            print(" Silicon Labs")
        else:
            print("")
        print("ProdID/TypeID={0:02X}:{1:02X}".format(man_prod_type,man_prod_type_id))
        pkt=self.Send2ZWave(FUNC_ID_ZW_GET_VERSION,True)  # SDK version
        (VerStr, lib) = unpack("!12sB", pkt[1:])
        VersionKey=VerStr[-5:-1]
        if VersionKey in ZWAVE_VER_DECODE:
            print("{} = {}".format(VerStr,ZWAVE_VER_DECODE[VersionKey]))
        else:
            print("Z-Wave version unknown = {}".format(VerStr))
        print("Library={} {}".format(lib,libType[lib]))
        pkt=self.Send2ZWave(FUNC_ID_SERIAL_API_GET_INIT_DATA,True)
        if pkt!=None and len(pkt)>33:
            print("NodeIDs=", end='')
            for k in [4,28+4]:
                j=pkt[k] # this is the first 8 nodes
                for i in range(0,8):
                    if (1<<i)&j:
                        print("{},".format(i+1+ 8*(k-4)),end='')
            print(" ",flush=True)
        if lib<7: # 700 series is not updateable via OTW - Use the bootloader instead
            pkt=self.Send2ZWave(FUNC_ID_ZW_FIRMWARE_UPDATE_NVM + FIRMWARE_UPDATE_NVM_INIT,True)
            if pkt==None:
                print("Enable to get firmware supported data")
                exit()
            (cmd, FirmwareUpdateSupported) = unpack("!BB", pkt[1:])
        else:
            FirmwareUpdateSupported=0x00
        if FirmwareUpdateSupported!=0x01:
            print("Firmware is not OTW capable - exiting {}".format(FirmwareUpdateSupported))
            exit()
        if self.filename=="":        # Skip OTW if no hex file is on the command line - just exit
            exit()

    def usage():
        print("")
        print("Usage: python ZWaveOTW.py [filename] [COMxx]")
        print("Version {}".format(VERSION))
        print("Filename is the name of the hex file to be programmed into the Z-Wave Interface")
        print("Filename must not contain the strings 'COM' or 'tty'")
        print("If Filename is not included then the version of the Z-Wave Interface is printed")
        print("COMxx is the Z-Wave UART interface - typically COMxx for windows and /dev/ttyXXXX for Linux")
        print("")

if __name__ == "__main__":
    ''' Start the app if this file is executed'''
    try:
        self=ZWaveOTW()
    except:
        print('error - unable to start program')
        ZWaveOTW.usage()
        exit()

    # fetch and display various attributes of the Controller - these are not required
    self.PrintVersion()

    # read in the hex file
    blank=IntelHex()
    for i in range (0,128*1024):
        blank[i]=255
    try:
        ih = IntelHex(self.filename)        # read in the file
    except:
        print("Failed to open {}".format(self.filename))
        self.usage()
        exit()
    ih.merge(blank,overlap='ignore')         # fill the empty spaces of the .hex file with 0xFF

    # Begin the OTW process
    pkt=self.Send2ZWave(pack("BB",FUNC_ID_ZW_SET_RF_RECEIVE_MODE,0),True) # Turn off the Radio to avoid retries
    if DEBUG>6 and pkt!=None:
        retVal=unpack("B",pkt[1])
        if retVal:
            print("Radio is off")
        else:
            print("Radio is still on {:X}".format(retval))
    for offset in range(0,128*1024,32):     # send down the entire file
        mystr=""
        for i in range(0,32):
            mystr+=pack("B",ih[i+offset])   # pack 32 bytes
        pkt=self.Send2ZWave(pack("BBBBBBB32s",FUNC_ID_ZW_FIRMWARE_UPDATE_NVM,FIRMWARE_UPDATE_NVM_WRITE,(offset>>16)&0x0FF,(offset>>8)&0x0FF,offset&0x0FF,0, 32,mystr),True)   # write 32 bytes per block
        print("\b.",end='',flush=True)
        if pkt==None:
            print("Download Failed - No callback")
            exit()
        if ord(pkt[2])!=0x01 or ord(pkt[0])!=0x78 or ord(pkt[1])!=0x05: # Occasionally will get 0x00 which is OK - just keep going
            if debug>5: print("No change for this block: Expected 0x78, 0x05, 0x01, got {:02X}, {:02X}, {:02X} at address {:X}".format(ord(pkt[0]),ord(pkt[1]),ord(pkt[2]),offset))

    print("Wait - computing the CRC")
    pkt=self.Send2ZWave(pack("BB",FUNC_ID_ZW_FIRMWARE_UPDATE_NVM,FIRMWARE_UPDATE_NVM_IS_VALID_CRC16),True, 10000) # extend timeout as CRC takes several seconds
    if pkt==None:
        print("Failed to get a response to the Update NVM")
        retVal=0
    else:
        (retVal,crc16) = unpack("!BH",pkt[2:5])
    if DEBUG>9:print("RetVal={} CRC={}".format(retVal,crc16))

    if retVal!=0x01:
        print("CRC is not valid = {} - exiting".format(crc16))
        self.Send2ZWave(pack("B",FUNC_ID_SERIAL_API_SOFT_RESET),False)  # Reboot!
        exit()

    pkt=self.Send2ZWave(pack("BB",FUNC_ID_ZW_FIRMWARE_UPDATE_NVM,FIRMWARE_UPDATE_NVM_SET_NEW_IMAGE),True) # Set the bit that there is a new firmware image available
    if pkt==None:
        print("Failed to Set New Image")
        exit()
    retVal=unpack("!B",pkt[2])
    if retVal==0:
        print("Firmware NewImage already set {:X}".format(retVal))

    print("Rebooting the Z-Wave Interface - please wait...")
    self.Send2ZWave(pack("B",FUNC_ID_SERIAL_API_SOFT_RESET),False)  # Reboot!

    for i in range(30): # wait 30 seconds for the flash to be updated and reboot
        if self.UZB.inWaiting(): break  # Newer firmware will send a START upon power up indicating the chip is ready
        time.sleep(1)

    self.PrintVersion()
    print("Done")

    exit()

