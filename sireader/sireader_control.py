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

from .compat import int2byte
from .exceptions import SIReaderException, SIReaderTimeout
from .sireader import SIReader

__all__ = ["SIReaderControl"]


class SIReaderControl(SIReader):
    """Class for reading an SI Station configured as control in autosend mode."""

    def __init__(self, *args, **kwargs):
        super(type(self), self).__init__(*args, **kwargs)
        self._next_offset = None

    def poll_punch(self, timeout=0):
        """Polls for new punches.
        @return: list of (cardnr, punchtime) tuples, empty list if no new punches are available
        """

        if not self.proto_config["ext_proto"]:
            raise SIReaderException(
                'This command only supports stations in "Extended Protocol" '
                "mode. Switch mode first"
            )

        if not self.proto_config["auto_send"]:
            raise SIReaderException(
                'This command only supports stations in "Autosend" '
                "mode. Switch mode first"
            )

        punches = []
        while True:
            try:
                c = self._read_command(timeout=timeout)
            except SIReaderTimeout:
                break

            if c[0] == SIReader.C_TRANS_REC:
                cur_offset = SIReader._to_int(
                    c[1][SIReader.T_OFFSET : SIReader.T_OFFSET + 3]
                )
                if self._next_offset is not None:
                    while self._next_offset < cur_offset:
                        # recover lost punches
                        punches.append(self._read_punch(self._next_offset))
                        self._next_offset += SIReader.REC_LEN

                self._next_offset = cur_offset + SIReader.REC_LEN
            punches.append(
                (
                    self._decode_cardnr(c[1][SIReader.T_CN : SIReader.T_CN + 4]),
                    self._decode_time(c[1][SIReader.T_TIME : SIReader.T_TIME + 2]),
                )
            )
        else:
            raise SIReaderException(
                "Unexpected command %s received" % hex(byte2int(c[0]))
            )

        return punches

    def _read_punch(self, offset):
        """Reads a punch from the SI Stations backup memory.
        @param offset: Position in the backup memory to read
        @warning:      Only supports firmwares 5.55+ older firmwares have an incompatible record format!
        """
        c = self._send_command(
            SIReader.C_GET_BACKUP,
            SIReader._to_str(offset, 3) + int2byte(SIReader.REC_LEN),
        )
        return (
            self._decode_cardnr(b"\x00" + c[1][SIReader.BC_CN : SIReader.BC_CN + 3]),
            self._decode_time(c[1][SIReader.BC_TIME : SIReader.BC_TIME + 2]),
        )
