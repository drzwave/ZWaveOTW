# ZWaveOTW
Z-Wave Over-The-Wire (OTW) firmware update

This repository contains a simple Python script to update the firmware in a connected Z-Wave chip.
Typically the device is connected via a UART and on Linux this would be via /dev/ttyAMA0 or /dev/ttyACM0.

Most UZBs CANNOT be updated via OTW as they don't have the required external serial NVM.
So if you have a USB Z-Wave dongle (UZB) this program probably won't work.
To reprogram a UZB use the PC Programmer program available on the SiLabs web site.

# Usage:
```
python ZWaveOTW.py [filename.hex] [COMxx]
Filename.hex is the hex file name of the firmware to be downloaded to the Z-Wave interface
   If the .hex file is not included, then the Z-Wave interface version and other parameters are printed
   The .hex filename cannot contain the string "COM" or "tty"
COMxx is the COM port (windows) or /dev/ttyxx (linux) of the Z-Wave interface
``` 

# Theory of Operation
Many Z-Wave interfaces can have their firmware updated via the UART using OTW using this program.
The target device must have an external NVM to store the firmware image. If the device does not have the external NVM, the program will print a message letting you know it is not possible to update the firmware.

The firmware already on the Z-Wave interface must have a bootloader that is OTW capable. If the version of firmware is prior to X.XX, it will need to be updated to SDK 6.61.00 first, and then it can be further updated to the latest release. At version 6.61 the bootload was upgraded and is no longer compatible with the latest version. Thus, the intermediate version must be downloaded which will upgrade the bootloader itself. Then the final version can be downloaded.

- OTW process:
    - The serial port to the interface is opened
    - The interface is inspected and the version and other data is printed to the screen
    - If a .hex file is not on the command line, the program exits
    - The 128kB firmware image is initialized with 0xFF
    - The .hex file is opened and the firmware image updated
    - A ? is sent
    - The firmware is downloaded to the target interface
        - The Interface sends a FIRMWARE_UPDATE_Get
        - The python program responds with a FIRMWARE_UPDATE_REPORT with a block of the firmware image
        - This process continues until the entire image has been downloaded
    - The interface stores the firmware image in the external serial NVM
    - The interface runs a CRC check on the entire image
    - If the CRC passes, the ??? is set and a ??? command is sent to the python program indicating the image is good
    - A soft reset command is sent to the interface
    - The Z-Wave interface reboots, inspects the contents of the NVM, copies the code from the NVM to the internal flash and then reboots. This process typically takes about 2 seconds.
    - The new firmware should be running

# Contacts
- Eric Ryherd - drzwave@silabs.com - Author of this script
