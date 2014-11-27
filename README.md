vbuspy
======

A simple module to data log various solar collectors made by RESOL. It can be easily configured for many different product versions by providing the packet decoder with a python dict describing the values available. These can be found from the VBus specification by RESOL.

The decoder can be easily used with various data sources, like serial, network or ordinary files for testing. Some small sample data dumps are provided. They can be decoded with the provided example script as follows: `./example.py sample_file`

The sample files are from a DeltaSol BS Plus controller.

See the example for reference.