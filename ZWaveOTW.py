''' Z-Wave Over-The-Wire firmware update

    This Python program will attempt to update the firmware with the desired hex file.
    Note that the target MUST be OTW capable which means the interface MUST have a 2Mbit
    serial flash chip. Most UZBs do NOT have OTW capability and cannot be updated with 
    this program. Use the PC Programmer to update UZBs.

    This program is a DEMO only and is provided AS-IS and without support. 
    But feel free to copy and improve!
    This program can be used as a guide to implement you own firmware update in your
    language of choice.

    Usage: python ZWaveOTW.py [filename] [COMx]
    filename is the .HEX file of the firmware to be sent to the Z-Wave chip.
      If filename is not provided then the current version of the Z-Wave chip is printed.
    COMx is optional and is the COM port or /dev/tty* port of the Z-Wave interface.
    Tested using Python 2.7 - untested on Python 3

    Only 500 series Z-Wave chips have OTW. 300 series do not nor do the 400 series.

    The program has been tested and works on a Raspberry Pi with an EZZee Z-Wave interface 
    board plugged into the 40 pin header. Note that the RPi must have the UART swapped 
    with the BLE interface. The following lines must be in /boot/config.txt:
    #swap the UART so the good one goes to the GPIOs instead of the Bluetooth chip.
    enable_uart=1
    dtoverlay=pi3-miniuart-bt

   Resources:
   OTW reference material: https://www.silabs.com/community/wireless/z-wave/knowledge-base.entry.html/2018/12/19/gateway_z-wave_500-gSQb
   SerialAPI: https://www.silabs.com/documents/login/user-guides/INS12350-Serial-API-Host-Appl.-Prg.-Guide.pdf (or search "SerialAPI" on the silabs site)
'''

import serial           # serial port control
import sys
import time
import os
from struct            import * # PACK


COMPORT       = "/dev/ttyAMA0" # Serial port default

DEBUG         = 10     # higher values print out more debugging info - 0=off

# Handy defines mostly copied from ZW_transport_api.py
FUNC_ID_SERIAL_API_GET_INIT_DATA    = 0x02
FUNC_ID_SERIAL_API_APPL_NODE_INFORMATION = 0x03
FUNC_ID_SERIAL_API_GET_CAPABILITIES = 0x07
FUNC_ID_SERIAL_API_SOFT_RESET       = 0x08
FUNC_ID_ZW_GET_PROTOCOL_VERSION     = 0x09
FUNC_ID_ZW_SEND_DATA                = 0x13
FUNC_ID_ZW_GET_VERSION              = 0x15
FUNC_ID_ZW_ADD_NODE_TO_NETWORK      = 0x4A
FUNC_ID_ZW_REMOVE_NODE_FROM_NETWORK = 0x4B
FUNC_ID_ZW_FIRMWARE_UPDATE_NVM      = 0x78

# Z-Wave Library Types
ZW_LIB_CONTROLLER_STATIC  = 0x01
ZW_LIB_CONTROLLER         = 0x02
ZW_LIB_SLAVE_ENHANCED     = 0x03
ZW_LIB_SLAVE              = 0x04
ZW_LIB_INSTALLER          = 0x05
ZW_LIB_SLAVE_ROUTING      = 0x06
ZW_LIB_CONTROLLER_BRIDGE  = 0x07
ZW_LIB_DUT                = 0x08
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
ZW_LIB_AVREMOTE           : "AVREMOTE",
ZW_LIB_AVDEVICE           : "AVDEVICE" }

ADD_NODE_ANY       = 0x01
ADD_NODE_CONTROLLER= 0x02
ADD_NODE_SLAVE     = 0x03
ADD_NODE_EXISTING  = 0x04
ADD_NODE_STOP      = 0x05
ADD_NODE_SMART_START = 0x09
TRANSMIT_COMPLETE_OK      =0x00
TRANSMIT_COMPLETE_NO_ACK  =0x01 
TRANSMIT_COMPLETE_FAIL    =0x02 
TRANSMIT_ROUTING_NOT_IDLE =0x03
TRANSMIT_OPTION_ACK = 0x01
TRANSMIT_OPTION_AUTO_ROUTE = 0x04
TRANSMIT_OPTION_EXPLORE = 0x20
# SerialAPI defines
SOF = 0x01
ACK = 0x06
NAK = 0x15
CAN = 0x18
REQUEST = 0x00
RESPONSE = 0x01
# Most Z-Wave commands want the autoroute option on to be sure it gets thru. Don't use Explorer though as that causes unnecessary delays.
TXOPTS = TRANSMIT_OPTION_AUTO_ROUTE | TRANSMIT_OPTION_ACK
ZWAVE_VER_DECODE = {    # Z-Wave version to SDK decoder: https://www.silabs.com/products/development-tools/software/z-wave/embedded-sdk/previous-versions
        "6.01" : "SDK 6.81.00 09/2017",
        "5.02" : "SDK 6.71.02 07/2017",
        "4.61" : "SDK 6.71.01 03/2017",
        "4.60" : "SDK 6.71.00 01/2017",
        "4.62" : "SDK 6.61.01 04/2017",  # This is the INTERMEDIATE version?
        "4.33" : "SDK 6.61.00 04/2016",
        "4.54" : "SDK 6.51.10 02/2017",
        "4.38" : "SDK 6.51.09 07/2016",
        "4.34" : "SDK 6.51.08 05/2016",
        "4.24" : "SDK 6.51.07 02/2016",
        "4.05" : "SDK 6.51.06 06/2015 or SDK 6.51.05 12/2014",
        "4.01" : "SDK 6.51.04 05/2014",
        "3.99" : "SDK 6.51.03 07/2014",
        "3.95" : "SDK 6.51.02 05/2014",
        "3.92" : "SDK 6.51.01 04/2014",
        "3.83" : "SDK 6.51.00 12/2013",
        "3.83" : "SDK 6.51.00 12/2013"
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
        if DEBUG>3: print "COM Port set to {}".format(self.COMPORT)
        if DEBUG>3: print "Filename set to {}".format(self.filename)
        try:
            self.UZB= serial.Serial(self.COMPORT,'115200',timeout=2)
        except serial.SerialException:
            print "Unable to open serial port {}".format(self.COMPORT)
            exit()

    def checksum(self,pkt):
        ''' compute the Z-Wave SerialAPI checksum at the end of each frame'''
        s=0xff
        for c in pkt:
            s ^= ord(c)
        return s

    def GetRxChar( self, timeout=100):
        ''' Get a character from the UART or timeout in 100ms'''
        while timeout >0 and not self.UZB.inWaiting():
            time.sleep(0.001)
            timeout -=1
        if timeout>0:
            retval= self.UZB.read()
        else:
            retval= None
        return retval

    def GetZWave( self, timeout=5000):
        ''' Receive a frame from the UART and return the binary string or timeout in TIMEOUT ms and return None'''
        pkt=""
        c=self.GetRxChar(timeout)
        if c == None:
            if DEBUG>1: print "GetZWave Timeout!"
            return None
        while ord(c)!=SOF:   # get synced on the SOF
            if DEBUG>5: print "SerialAPI Not SYNCed {:02X}".format(ord(c))
            c=self.GetRxChar(timeout)
        if ord(c)!=SOF:
            return None
        length=ord(self.GetRxChar())
        for i in range(length):
            c=self.GetRxChar()
            pkt += c
        checksum= self.checksum(pkt)
        checksum ^= length  # checksum includes the length
        if checksum!=0:
            if DEBUG>1: print "GetZWave checksum failed {:02x}".format(checksum)
        self.UZB.write(pack("B",ACK))  # ACK the returned frame - we don't send anything else even if the checksum is wrong
        return pkt[1:-1] # strip off the type and checksum
 
 
    def Send2ZWave( self, SerialAPIcmd, returnStringFlag=False):
        ''' Send the command via the SerialAPI to the Z-Wave chip and optionally wait for a response.
            If ReturnStringFlag=True then returns a binary string of the SerialAPI frame response
            else returns None
            Waits for the ACK/NAK/CAN for the SerialAPI and strips that off.
            Removes all SerialAPI data from the UART before sending and ACKs to clear any retries.
        '''
        if self.UZB.inWaiting(): 
            self.UZB.write(pack("B",ACK))  # ACK just to clear out any retries
            print "Dumping ",
        while self.UZB.inWaiting(): # purge UART RX to remove any old frames we don't want
            c=self.UZB.read()
            if DEBUG>9: print " {:02X}".format(ord(c)),
        frame = pack("2B", len(SerialAPIcmd)+2, REQUEST) + SerialAPIcmd # add LEN and REQ bytes which are part of the checksum
        chksum= self.checksum(frame)
        pkt = (pack("B",SOF) + frame + pack("B",chksum)) # add SOF to front and CHECKSUM to end
        for c in pkt:
            self.UZB.write(c)  # send the command
        # should always get an ACK/NAK/CAN so wait for it here
        c=self.GetRxChar(500) # wait up to half second for the ACK
        if c==None:
            if DEBUG>1: print "Error - no ACK or NAK"
        elif ord(c)!=ACK:
            if DEBUG>1: print "Error - not ACKed = 0x{:02X}".format(ord(c))
            if ord(c)==CAN:
                self.UZB.write(pack("B",ACK))   # send an ACK to try to clear the CAN
                time.sleep(1)
                for c in pkt:
                    self.UZB.write(c) # resend the command
                c=self.GetRxChar(500) # Just drop the ACK this time thru
                if DEBUG>1: print "Second ACK=0x{:02X}".format(ord(c))
        response=None
        if returnStringFlag:    # wait for the returning frame for up to 5 seconds
            response=self.GetZWave()    
        return response
            

    def RemoveLifeline( self, NodeID):
        ''' Remove the Lifeline Association from the NodeID (integer). 
            Helps eliminate interfering traffic being sent to the controller during the middle of range testing.
        '''
        pkt=self.Send2ZWave(pack("!9B",FUNC_ID_ZW_SEND_DATA, NodeID, 4, 0x85, 0x04, 0x01, 0x01, TXOPTS, 78),True)
        pkt=self.GetZWave(10*1000)
        if pkt==None or ord(pkt[2])!=0:
            if DEBUG>1: print "Failed to remove Lifeline"
        else:
            print "Lifeline removed"
        if DEBUG>12: 
            for i in range(len(pkt)): 
                print "{:02X}".format(ord(pkt[i])),

    def mainloop(self):             # TODO expecting to dump all of this as this program is just command line
        line = raw_input('>')
        if len(line)<1: line=' '
        while line[0]!='x' or 'exit' in line:     # Exit when you enter X
            if line[0]=='z':    # Get the SerialAPI version - basic check that the UZB is working
                pkt=self.Send2ZWave(pack("B",FUNC_ID_SERIAL_API_GET_CAPABILITIES),True)
                if len(pkt)<37 or len(pkt)>46: # should be 41 bytes - if not, try again
                    pkt=self.Send2ZWave(pack("B",FUNC_ID_SERIAL_API_GET_CAPABILITIES),True)
                (ver, rev, man_id, man_prod_type, man_prod_type_id, supported) = unpack("!2B3H32s", pkt[1:])
                print "SerialAPI Ver={0}.{1}".format(ver,rev)
                if (man_id==0x001E):
                    print "Mfg=Express Controls"
                else:
                    print "Mfg={:04X}".format(man_id)
                print "ProdID/TypeID={0:02X}:{1:02X}".format(man_prod_type,man_prod_type_id)
                pkt=self.Send2ZWave(pack("B",FUNC_ID_SERIAL_API_GET_INIT_DATA),True)
                if pkt!=None and len(pkt)>33:
                    print "NodeIDs=",
                    for k in [4,28+4]:
                        j=ord(pkt[k]) # this is the first 8 nodes
                        for i in range(0,8):
                            if (1<<i)&j:
                                print "{},".format(i+1+ 8*(k-4)),
                print " "
            elif 'Table' in line: # Assign the TurnTable NodeID
                linesplit=line.split()
                self.TableNodeID=int(linesplit[1])
                print 'TurnTable NodeID set to {}'.format(self.TableNodeID)
            elif 'DUT' in line: # Assign the DevKit NodeID
                linesplit=line.split()
                self.DUTNodeID=int(linesplit[1])
                print 'Dut NodeID set to {}'.format(self.DUTNodeID)
            elif 'DevKit' in line: # Assign the DevKit NodeID
                linesplit=line.split()
                self.DevKitNodeID=int(linesplit[1])
            elif 'Orient' in line: # change the number of orientations
                linesplit=line.split()
                self.NumberOfOrientations=int(linesplit[1])
                print 'Orientations set to {}'.format(self.NumberOfOrientations)
            elif line[0]=='l': # Remove the lifeline from the DevKit NodeID
                self.RemoveLifeline(self.DevKitNodeID)
                self.RemoveLifeline(self.TableNodeID)
            elif line[0]=='r': # Range test
                result=self.RunRangeTest(self.NumberOfNOPs)
                print result
            elif line[0]=='o': # Run all orientations
                linesplit=line.split()
                if len(linesplit)!=2:
                    print "need a distance - o xxx - where xxx is the distance between the DevKit and the DUT"
                else:
                    self.RunOrientations(self.NumberOfOrientations,linesplit[1])
            elif line[0]=='0': # Set the rotating table to 0 degrees
                pkt=self.Send2ZWave(pack("!8B",FUNC_ID_ZW_SEND_DATA, self.TableNodeID, 3, 0x20, 0x01, 0, TXOPTS, 79),True) # Basic Set of 0%
                pkt=self.GetZWave(1000)
            elif line[0]=='1': # Set the rotating table to 90 degrees
                pkt=self.Send2ZWave(pack("!8B",FUNC_ID_ZW_SEND_DATA, self.TableNodeID, 3, 0x20, 0x01, 25, TXOPTS, 79),True)
                pkt=self.GetZWave(1000)
            elif line[0]=='2': # Set the rotating table to 180 degrees
                pkt=self.Send2ZWave(pack("!8B",FUNC_ID_ZW_SEND_DATA, self.TableNodeID, 3, 0x20, 0x01, 50, TXOPTS, 79),True)
                pkt=self.GetZWave(1000)
            elif line[0]=='3': # Set the rotating table to 270 degrees
                pkt=self.Send2ZWave(pack("!8B",FUNC_ID_ZW_SEND_DATA, self.TableNodeID, 3, 0x20, 0x01, 75, TXOPTS, 79),True)
                pkt=self.GetZWave(1000)
            elif line[0]=='+': # inclusion mode
                pkt=self.Send2ZWave(pack("3B",FUNC_ID_ZW_ADD_NODE_TO_NETWORK, ADD_NODE_ANY, 0xaa),True)
                (cmd,FuncID,bStatus)= unpack("BBB",pkt[:3]) # first status should be 01=learn_ready
                if (bStatus==ADD_NODE_STATUS_LEARN_READY):
                    print "Press Button on Device"
                while not (bStatus==ADD_NODE_STATUS_FAILED or bStatus==ADD_NODE_STATUS_DONE): # will get several callbacks until DONE with info along the way
                    pkt=self.GetZWave(50*1000)      # wait for up to 50seconds for a response
                    (cmd,FuncID,bStatus)= unpack("BBB",pkt[:3])
                    #print "Adding Status={}".format(bStatus)
                    if bStatus==ADD_NODE_STATUS_PROTOCOL_DONE: # required to send it again to get to DONE
                        pkt=self.Send2ZWave(pack("3B",FUNC_ID_ZW_ADD_NODE_TO_NETWORK, ADD_NODE_STOP, 0xaa),False)
                    if (bStatus==ADD_NODE_STATUS_ADDING_SLAVE or bStatus==ADD_NODE_STATUS_ADDING_CONTROLLER):
                        stuff,=unpack("B",pkt[3])
                        print "Added Node {}".format(stuff)
                if bStatus==ADD_NODE_STATUS_FAILED:
                    print "Add node failed"
                self.Send2ZWave(pack("BB",FUNC_ID_ZW_ADD_NODE_TO_NETWORK, ADD_NODE_STOP),False) # cleanup
            elif line[0]=='-': # exclusion mode
                pkt=self.Send2ZWave(pack("3B",FUNC_ID_ZW_REMOVE_NODE_FROM_NETWORK, REMOVE_NODE_ANY, 0xdd),True) # go into exclude mode but wait up to 60 seconds for a response
                (cmd,FuncID,bStatus)= unpack("BBB",pkt[:3]) # first status should be 01=learn_ready
                if (bStatus==REMOVE_NODE_STATUS_LEARN_READY):
                    print "Press Button on Device"
                while not (bStatus==REMOVE_NODE_STATUS_FAILED or bStatus==REMOVE_NODE_STATUS_DONE): # will get several callbacks until DONE with info along the way
                    pkt=self.GetZWave(50*1000)      # wait for up to 50seconds for a response
                    (cmd,FuncID,bStatus)= unpack("BBB",pkt[:3])
                    if (bStatus==REMOVE_NODE_STATUS_REMOVING_SLAVE or bStatus==REMOVE_NODE_STATUS_REMOVING_CONTROLLER):
                        stuff,=unpack("B",pkt[3])
                        print "Excluded Node {}".format(stuff)
                self.Send2ZWave(pack("BB",FUNC_ID_ZW_REMOVE_NODE_FROM_NETWORK, REMOVE_NODE_STOP),False) # cleanup
            elif line[0]=='q' or line[0]=='x':
                return
            elif line[0]=='?':
                self.usage()
            line = raw_input('>') # get the next command
            if len(line)<1: line=' '    # if the user just hit <CR> ignore it
        return

    def usage(self):
        print "Usage: python ZWaveOTW.py [filename] [COMxx]"
        print "Version 0.10  18 Jan 2019"
        print ""

if __name__ == "__main__":
    ''' Start the app if this file is executed'''
    try:
        self=ZWaveOTW()
    except:
        print 'error - unable to start program'
        exit()

    # fetch and display various attributes of the Controller - these are not required
    pkt=self.Send2ZWave(pack("B",FUNC_ID_SERIAL_API_GET_CAPABILITIES),True)
    (ver, rev, man_id, man_prod_type, man_prod_type_id, supported) = unpack("!2B3H32s", pkt[1:])
    print "SerialAPI Ver={0}.{1}".format(ver,rev)   # SerialAPI version is different than the SDK version
    print "Mfg={:04X}".format(man_id)
    print "ProdID/TypeID={0:02X}:{1:02X}".format(man_prod_type,man_prod_type_id)
    pkt=self.Send2ZWave(pack("B",FUNC_ID_ZW_GET_VERSION),True)  # SDK version
    (VerStr, lib) = unpack("!12sB", pkt[1:])
    print "{} {}".format(VerStr,ZWAVE_VER_DECODE[VerStr[-5:-1]])
    print "Library={} {}".format(lib,libType[lib])
    pkt=self.Send2ZWave(pack("B",FUNC_ID_SERIAL_API_GET_INIT_DATA),True)
    if pkt!=None and len(pkt)>33:
        print "NodeIDs=",
        for k in [4,28+4]:
            j=ord(pkt[k]) # this is the first 8 nodes
            for i in range(0,8):
                if (1<<i)&j:
                    print "{},".format(i+1+ 8*(k-4)),
        print " "
    pkt=self.Send2ZWave(pack("BB",FUNC_ID_ZW_FIRMWARE_UPDATE_NVM,0x00),True)
    (cmd, FirmwareUpdateSupported) = unpack("!BB", pkt[1:])
    if FirmwareUpdateSupported!=0x01:
        print "Firmware is not OTW capable - exiting {}".format(FirmwareUpdateSupported)
        exit()
    if self.filename=="":        # Skip OTW if no hex file is on the command line
        exit()

    # Begin the OTW process

    exit()

