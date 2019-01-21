This directory contains a few versions of the Z-Wave Static Controller SerialAPI.
These are here just for testing purposes.
Please download the latest version from the Z-Wave web site.

The hex file typically needed is in the SDK/ProductPlus/bin/SerialAPI_Static directory though you may want one of the other libraries like the _Bridge to use Z/IP Gateway.
The file in that directory depends on the frequency.
The filename MUST have OTW in the name. 
If you are using the USB port, use the USBVP files otherwise if using the UART use the ones without USBVP.
Use only the .OTZ files. The .HEX files are for programming the chip the first time including the bootloader.
