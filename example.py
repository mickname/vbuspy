#!/usr/bin/env python

from __future__ import division

import sys, os, select
import json

from vbus import VbusStreamDecoder


# These options are model specific and are for Resol DeltaSol BS Plus

all_opts = {
	'S1': {
		'type': 'numeric',
		'multiplier': 0.1,
		'frame': 0,
		'bytes': [0, 1]
	},
	'S2': {
		'type': 'numeric',
		'multiplier': 0.1,
		'frame': 0,
		'bytes': [2, 3]
	},
	'S3': {
		'type': 'numeric',
		'multiplier': 0.1,
		'frame': 1,
		'bytes': [0, 1]
	},
	'S4': {
		'type': 'numeric',
		'multiplier': 0.1,
		'frame': 1,
		'bytes': [2, 3]
	}, 'Speed1': {
		'type': 'numeric',
		'multiplier': 1,
		'frame': 2,
		'bytes': [0]
	}, 'Speed2': {
		'type': 'numeric',
		'multiplier': 1,
		'frame': 2,
		'bytes': [1]
	}, 'Time': {
		'type': 'time',
		'frame': 3,
		'offset': 0
	}, 'Energy': {
		'type': 'compound',
		'parts': [
			{'frame': 5, 'bytes': [0, 1], 'multiplier': 1},
			{'frame': 5, 'bytes': [2, 3], 'multiplier': 1000},
			{'frame': 6, 'bytes': [0, 1], 'multiplier': 1000000}
		]
	}, 'Relays': {
		'type': 'bitmask',
		'frame': 2,
		'offset': 2
	}, 'Errors': {
		'type': 'bitmask',
		'frame': 2,
		'offset': 3
	}
	
}

# decode only the temperatures ['S1', 'S2', 'S3', 'S4']
opts = { key: all_opts[key] for key in ['S1', 'S2', 'S3', 'S4'] }
# opts = all_opts



def vbus_packet_callback(packet):
	# 0x0100 == "Packet contains data for slave"
	if packet.command == 0x0100:
		print json.dumps(packet.decode_payload(opts), sort_keys=True)

def decoder_error_callback(msg):
	print msg

def main():
	fname = sys.argv[1]

	# Initialize the decoder.
	dec = VbusStreamDecoder(packet_handler=vbus_packet_callback,
	                        decoding_error_handler=decoder_error_callback)

	with open(fname, 'rb', 0) as f:
		fd = f.fileno()

		while True:
			# Wait for data to be available, with select we can read an ordinary
			# file and a character device (i.e. serial port) without reading
			# only a single byte at a time or blocking for longer than required.
			select.select([fd], [], [])

			data = os.read(fd, 512)

			if data:
				# Decode the data.
				dec.slurp(data)
			else:
				break


if __name__ == '__main__':
	if len(sys.argv) != 2:
		print "Need 1 argument: filename"
	else:
		main()



