#    Copyright (C) 2008-2014  Gaudenz Steinlin <gaudenz@durcheinandertal.ch>
#                       2014  Simon Harston <simon@harston.de>
#                       2015  Jan Vorwerk <jan.vorwerk@angexis.com>
#                       2019  Per Magnusson <per.magnusson@gmail.com>
#                       2023  Per Magnusson <per.magnusson@gmail.com>
#                       2024  Simeon Doetsch <mail@simske.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

from serial.serialutil import SerialException

from .compat import int2byte
from .exceptions import SIReaderCardChanged, SIReaderException
from .sireader import SIReader

__all__ = "SIReaderReadout"


class SIReaderReadout(SIReader):
    """Class for 'classic' SI card readout. Reads out the whole card. If you don't know
    about other readout modes (control mode) you probably want this class."""

    def __init__(self, *args, **kwargs):
        super(type(self), self).__init__(*args, **kwargs)

        self.sicard = None
        self.cardtype = None

    def poll_sicard(self):
        """Polls for an SI-Card inserted or removed into the SI Station.
        Returns true on state changes and false otherwise. If other commands
        are received an Exception is raised."""

        if not self.proto_config["ext_proto"]:
            raise SIReaderException(
                'This command only supports stations in "Extended Protocol" '
                "mode. Switch mode first"
            )

        if not self.proto_config["mode"] == SIReader.M_READOUT:
            raise SIReaderException(
                "Station must be in 'Read SI cards' operating mode! Change operating mode first."
            )

        if self._serial.inWaiting() == 0:
            return False

        oldcard = self.sicard
        while self._serial.inWaiting() > 0:
            # _read_command does the actual parsing of the command
            # if it's an insert or remove event
            try:
                self._read_command(timeout=0)
            except SIReaderCardChanged:
                pass

        return not oldcard == self.sicard

    def read_sicard(self, reftime=None):
        """Reads out the SI Card currently inserted into the station. The card must be
        detected with poll_sicard before."""

        if not self.proto_config["ext_proto"]:
            raise SIReaderException(
                'This command only supports stations in "Extended Protocol" '
                "mode. Switch mode first"
            )

        if not self.proto_config["mode"] == SIReader.M_READOUT:
            raise SIReaderException(
                "Station must be in 'Read SI cards' operating mode! Change operating mode first."
            )

        if self.cardtype == "SI5":
            raw_data = self._send_command(SIReader.C_GET_SI5, b"")[1]
        elif self.cardtype == "SI6":
            raw_data = self._send_command(SIReader.C_GET_SI6, SIReader.P_SI6_CB)[1][1:]
            raw_data += self._read_command()[1][1:]
            raw_data += self._read_command()[1][1:]
        elif self.cardtype in ("SI8", "SI9", "pCard"):
            raw_data = b""
            for b in range(SIReader.CARD[self.cardtype]["BC"]):
                raw_data += self._send_command(SIReader.C_GET_SI9, int2byte(b))[1][1:]

        elif self.cardtype == "SI10":
            # Reading out SI10 cards block by block proved to be unreliable and slow
            # Thus reading with C_GET_SI9 and block number 8 = P_SI6_CB like SI6
            # cards
            raw_data = self._send_command(SIReader.C_GET_SI9, SIReader.P_SI6_CB)[1][1:]
            raw_data += self._read_command()[1][1:]
            raw_data += self._read_command()[1][1:]
            raw_data += self._read_command()[1][1:]
            raw_data += self._read_command()[1][1:]
        else:
            raise SIReaderException("No card in the device.")

        return SIReader._decode_carddata(raw_data, self.cardtype, reftime)

    def ack_sicard(self):
        """Sends an ACK signal to the SI Station. After receiving an ACK signal
        the station blinks and beeps to signal correct card readout."""
        try:
            self._serial.write(SIReader.ACK)
        except (SerialException, OSError) as msg:
            raise SIReaderException("Could not send ACK: %s" % msg)

    def _read_command(self, timeout=None):
        """Reads commands from the station. As a station in readout mode can send a
        card inserted or card removed event at any time we have to intercept these events
        here."""
        cmd, data = super(type(self), self)._read_command(timeout)

        # check if a card was inserted or removed
        if cmd == SIReader.C_SI_REM:
            self.sicard = None
            self.cardtype = None
            raise SIReaderCardChanged("SI-Card removed during command.")
        elif cmd == SIReader.C_SI5_DET:
            self.sicard = self._decode_cardnr(data)
            self.cardtype = "SI5"
            raise SIReaderCardChanged("SI-Card inserted during command.")
        elif cmd == SIReader.C_SI6_DET:
            self.sicard = self._to_int(data)
            self.cardtype = "SI6"
            raise SIReaderCardChanged("SI-Card inserted during command.")
        elif cmd == SIReader.C_SI9_DET:
            # SI 9 sends corrupt first byte (insignificant)
            self.sicard = self._to_int(data[1:])
            if self.sicard >= 2000000 and self.sicard <= 2999999:
                self.cardtype = "SI8"
            elif self.sicard >= 1000000 and self.sicard <= 1999999:
                self.cardtype = "SI9"
            elif self.sicard >= 4000000 and self.sicard <= 4999999:
                self.cardtype = "pCard"
            #            elif self.sicard >= 6000000 and self.sicard <= 6999999:  # tCard, don't have one for testing
            #                self.cardtype = 'SI9'
            elif self.sicard >= 7000000 and self.sicard <= 9999999:
                self.cardtype = "SI10"
            else:
                raise SIReaderException("Unknown cardtype!")
            raise SIReaderCardChanged("SI-Card inserted during command.")

        return (cmd, data)
