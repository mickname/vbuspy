#!/usr/bin/env python

from __future__ import division


class VbusPacket(object):
	"""Represents a single VBus data packet"""

	def __init__(self, data):
		self.destination_address = data[0] + data[1] << 8
		self.source_address = data[2] + data[3] << 8
		self.protocol_version = data[4]
		self.command = data[5] + data[6] << 8
		self.frame_count = data[7]
		self.frames = []

		# Sum of the data bytes inverted (but no MSB)
		calculated_checksum = ~sum(data[0:8]) & 0x0000007F

		if calculated_checksum != data[8]:
			raise ValueError("Checksum mismatch: 0x%02x != 0x%02x" % (data[8], calculated_checksum))

	def decode_frames(self, data):
		if len(data) != 6 * self.frame_count:
			raise IndexError("Frame count and amount of data do not match")

		for i in range(self.frame_count):
			offset = i * 6

			calculated_checksum = ~sum(data[offset:offset + 5]) & 0x0000007F

			checksum = data[offset + 5]

			if (checksum  != calculated_checksum):
				raise ValueError("Checksum mismatch in frame %d: 0x%02x != 0x%02x" % (i + 1, checksum, calculated_checksum))

			frame = (
				data[offset + 0] | (data[offset + 4] & 0x01) << 7,
				data[offset + 1] | (data[offset + 4] & 0x02) << 6,
				data[offset + 2] | (data[offset + 4] & 0x04) << 5,
				data[offset + 3] | (data[offset + 4] & 0x08) << 4
			)

			self.frames.append(frame)


	def decode_number(self, frame, byte_range, multiplier=1, unsigned=False):
		"""Decode a number given a frame and range of bytes from low to high."""
		value = 0

		byte_count = len(byte_range)

		for byte_number, offset in enumerate(byte_range):
			raw_byte = self.frames[frame][offset]

			if not unsigned:
				# High byte may have negative sign, others are considered unsigned
				if byte_number == byte_count - 1 and raw_byte > 127:
					raw_byte = raw_byte - 256


			value = value + (raw_byte << (byte_number * 8))

		return value * multiplier

	def decode_payload(self, decoding_instructions):
		"""Returns a dict containing the decoded data, decoded with the dict
		decoding_instructions.
		"""

		out = {}

		for name, structure in decoding_instructions.iteritems():
			if structure['type'] == 'numeric':
				out[name] = self.decode_number(structure['frame'], structure['bytes'], structure['multiplier'])
			elif structure['type'] == 'time':
				minutes = self.decode_number(structure['frame'], [structure['offset'], structure['offset'] + 1])
				out[name] = "%d:%d" % (minutes // 60, minutes % 60)
			elif structure['type'] == 'compound':
				total = 0
				for part in structure['parts']:
					total = total + self.decode_number(part['frame'], part['bytes'], part['multiplier'])
				out[name] = total
			elif structure['type'] == 'bitmask':
				mask = self.decode_number(structure['frame'], [structure['offset']], unsigned=True)
				out[name] = format(mask, '08b')

		return out

	def __str__(self):
		return "<VbusPacket to 0x%x from 0x%x, command: 0x%x, %d frames>" % (self.destination_address, self.source_address, self.command, self.frame_count)


class VbusDatagram(object):
	"""Represents a VBus datagram. Not implemented."""

	def __init__(self):
		raise NotImplementedError("VBus Datagrams are not supported yet")


class DecoderState:
	WAIT_SYNC = 1
	DETECT_HEADER_TYPE = 2
	DECODE_HEADER1 = 3
	DECODE_HEADER2 = 4
	DECODE_FRAMES = 5


class VbusStreamDecoder(object):
	HEADER_STUB_LENGTH = 5
	HEADER_1_LENGTH = 9
	HEADER_2_LENGTH = 15
	FRAME_LENGTH = 6

	def __init__(self, packet_handler=None, datagram_handler=None, decoding_error_handler=None):
		"""Form a decoder for a VBus data stream.

		packet_handler:
			Callback function which is called when a new packet has been
			decoded from the input with the packet as a	parameter.
		datagram_handler:
			Callback function which is called when a new datagram has been
			decoded.
		decoding_error_handler:
			Callback function which is called when an error occurs. The
			parameter is a textual description of the error - useful mainly for
			logging.
		"""

		self.packet_handler = packet_handler
		self.datagram_handler = datagram_handler
		self.decoding_error_handler = decoding_error_handler

		self.buf = []
		self.state = DecoderState.WAIT_SYNC
		self.vbuspacket = None

	def _dispatch_error(self, msg):
		if self.decoding_error_handler:
			self.decoding_error_handler(msg)

	def slurp(self, data):
		"""Processes the input data stream.

		Call with a buffer of input bytes and the callbacks are called as it is
		decoded.
		"""

		for b in data:
			numeric_b = ord(b)

			if numeric_b == 0xAA:
				# Sync start
				self.state = DecoderState.DETECT_HEADER_TYPE
				self.buf = []
			elif numeric_b & 0x80:
				# MSB set but not 0xAA, corrupt data
				self.state = DecoderState.WAIT_SYNC
				self.buf = [] # Clear thebuffer
				self._dispatch_error("Received a byte with MSB set")

			else:
				# Add the input byte to the internal buffer
				self.buf.append(numeric_b)

				# State after receiving sync byte
				if self.state == DecoderState.DETECT_HEADER_TYPE:
					if len(self.buf) == VbusStreamDecoder.HEADER_STUB_LENGTH:
						proto_version = self.buf[4]

						if proto_version == 0x10:
							# Protocol 1.0 "Packets"
							self.state = DecoderState.DECODE_HEADER1
						elif proto_version == 0x20:
							# Protocol 2.0 "Datagrams"
							self.state = DecoderState.DECODE_HEADER2
						elif proto_version == 0x30:
							# Protocol 3.0, not supported
							self._dispatch_error("Protocol version 3.0 is not supported")
							self.state = DecoderState.WAIT_SYNC
							self.buf = [] 
						else:
							self._dispatch_error("Unrecognized protocol version: 0x%x" % proto_version)
							self.state = DecoderState.WAIT_SYNC
							self.buf = []

				# Decode protocol 1.0 header
				elif self.state == DecoderState.DECODE_HEADER1:
					if len(self.buf) == VbusStreamDecoder.HEADER_1_LENGTH:
						try:
							self.vbuspacket = VbusPacket(self.buf)
							self.state = DecoderState.DECODE_FRAMES
						except ValueError as e:
							self._dispatch_error("Decoding VBus packet failed:: %s" % e)
							self.state = DecoderState.WAIT_SYNC
							
						self.buf = []

				# Decode protocotocol 1.0 frames
				elif self.state == DecoderState.DECODE_FRAMES:
					if len(self.buf) == self.vbuspacket.frame_count * VbusStreamDecoder.FRAME_LENGTH:
						if self.packet_handler:
							try:
								self.vbuspacket.decode_frames(self.buf)
								self.packet_handler(self.vbuspacket)
							except (ValueError, IndexError) as e:
								self._dispatch_error("Decoding VBus frame failed: %s" % e)

						self.vbuspacket = None

						self.state = DecoderState.WAIT_SYNC
						self.buf = []

				# Decode protocol 2.0 header
				elif self.state == DecoderState.DECODE_HEADER2:
					if len(self.buf) == VbusStreamDecoder.HEADER_2_LENGTH:
						if self.datagram_handler:
							# raises a NotImplementedError
							self.datagram_handler(VbusDatagram())

						self.state = DecoderState.WAIT_SYNC
						self.buf = []
