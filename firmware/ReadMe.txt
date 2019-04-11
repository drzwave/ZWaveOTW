This directory contains a few versions of the Z-Wave Static Controller SerialAPI.
These are here just for testing purposes.
Please download the latest version from the Z-Wave web site.

The hex file typically needed is in the SDK/ProductPlus/bin/SerialAPI_Static directory though you may want one of the other libraries like the _Bridge to use Z/IP Gateway.
The file in that directory depends on the frequency.
The filename MUST have OTW in the name. 
If you are using the USB port, use the USBVP files otherwise if using the UART use the ones without USBVP.
Use only the .OTZ files. 
The .HEX files are for programming the chip the first time including the bootloader.


When upgrading from the 6.51 or earlier releases, you MUST first OTA to:
serialapi_controller_static_OTU_ZW050x_US_6.61.01_intermediate.ota
which will update the bootloader to the new .OTZ file format.
Then you can update to newer versions of the SDK.

Note that prior to 6.61 there are separate files for ZM5202 and other Z-Wave chips
as the limited pinout of the ZM5202 requires a different firmware load.
Later release are able to handle this automatically via settings in the NVR.
