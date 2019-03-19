# ZWaveOTW
Z-Wave Over-The-Wire (OTW) firmware update

This repository contains a simple Python script to update the firmware in a connected Z-Wave chip.
Typically the device is connected via a UART. On Linux this would be via /dev/ttyAMA0 or /dev/ttyACM0.
On a PC it would be via COMxx. 

Most UZBs CANNOT be updated via OTW as they don't have the required external serial NVM.
So if you have a USB Z-Wave dongle (UZB) this program probably won't work.
To reprogram a UZB use the PC Programmer application available on the SiLabs web site.

The program was tested using a Rasberry Pi with a ZM5202 connected to the GPIO pins of the UART.

Feel free to copy and improve. NO SUPPORT IS PROVIDED! This program is provided by the author AS-IS. 

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

The firmware already on the Z-Wave interface must have a bootloader that is OTW capable. If the version of firmware is prior to 6.61, it will need to be updated to SDK 6.61.00 first, and then it can be further updated to the latest release. At version 6.61 the bootloader was upgraded and is no longer compatible with the latest version. Thus, the intermediate version must be downloaded which will upgrade the bootloader itself. Then the final version can be downloaded.

- OTW process:
    - The serial port to the interface is opened
    - The interface is inspected and the version and other data is printed to the screen
    - If a .hex file is not on the command line, the program exits
    - The 128kB firmware image is initialized with 0xFF
    - The .hex file is opened and overlaid onto the firmware image
    - The radio is turned off otherwise the UART will often overflow and cause retries
    - The FUNC_ID_ZW_FIRMWARE_UPDATE_NVM with command FIRMWARE_UDPATE_NVM_INIT initializes the download
    - The firmware is downloaded to the 500 series chip
        1. The python program sends a FUNC_ID_ZW_FIRMWARE_UPDATE_NVM with 32 bytes of data
        2. Then waits for the callback that the 32 bytes were OK
        3. A '.' is printed for each block of data. If a retry is required a message is printed. Retrys are common if there is Z-Wave traffic during the download.
        4. Return to step 1 until the entire image has been downloaded which takes about 60 seconds
    - A FIRMWARE_UPDATE_NVM_IS_VALID_CRC16 command checks the contents of the downloaded image (this takes several seconds)
    - A FIRMWARE_UPDATE_NVM_SET_NEW_IMAGE command sets the bit to reboot into the new image
    - A FUNC_ID_SERIAL_API_SOFT_RESET command is sent to reboot the 500 series chip
    - The Z-Wave chip reboots, inspects the contents of the NVM, if the CRC is OK, it copies the code from the NVM to the internal flash and then reboots. This process typically takes about 15 seconds.
    - The new firmware should be running and the new version is printed

If the chip loses power or some sort of error occurs in the short time window while the chip is copying the data from the NVM to internal flash, it is likely the chip will Brick and then be completely unusable. Note that this is a narrow time window of only a few seconds and is not reliant on any communication with the Python program so it is unlikely to brick.

The FIRMWARE directory contains several sets of firmware images that can be downloaded to the target to test this program.

# Contacts
- Eric Ryherd - drzwave@silabs.com - Author of this script

THIS PROGRAM IS PROVIDED AS-IS and WITHOUT SUPPORT! Feel free to copy and improve. See the License file for details.
