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
"""
sireader2.py - Classes to read out si card data and backup
memory from BSM-7/8 stations.
Also contains functions to read and modify the configuration of stations.
The code contains documentation of much of the communication protocol
used by Sportident stations.

Additions and modifications by Per Magnusson:
- A few more parts of the SYS_VAL structure were worked out and described.
- The format of the data when reading out the backup memory was reverse
  engineered and documented, both for stations in legacy and extended
  protocol modes.
- Added function to read out backup memory of stations in legacy and
  extended protocol modes.
- Added function to save the backup data to a CSV file of the same
  format as that used by Sportident Config+.
- Added functions to set the station in direct and remote mode.
- A wakeup byte is sent as default before packets to stations.
  This seems to make the communication more robust.
- Made the serial port search smarter for Windows.
- Fixed an issue with "raise StopIteration" in the _crc routine,
  which no longer works in Python 3.7 (PEP 479).
- Compatibility with Python 2 is probably no longer preserved.
- Added sysval_ functions to access configuration data in SYS_VAL.

"""

from __future__ import print_function

import csv
import os
import re
import sys
import threading
from binascii import hexlify
from datetime import datetime, timedelta
from typing import List, Literal, Optional, Tuple

import serial.tools.list_ports
from serial import Serial
from serial.serialutil import SerialException

from .compat import PY3, byte2int, int2byte, iterbytes
from .exceptions import SIReaderException, SIReaderTimeout
from .si_constants import SIConstants


class SIReader(SIConstants):
    """Base protocol functions and constants to interact with SI Stations.
    Protocol Constants are defined in SIConstants.
    """

    def __init__(
        self,
        *,
        port: Optional[str] = None,
        debug: bool = False,
        noconnect: bool = False,
        lowspeed: bool = False,
        logfile: Optional[str] = None,
    ):
        """Initializes communication with SI station.

        Args:
            port (Optional[str]): The port to connect to. If not provided, the code will
                attempt to connect to all available serial ports.
            debug (bool): Enable debug mode. Defaults to False.
            noconnect (bool): Do not establish a connection to the SI station. Defaults
                to False.
            lowspeed (bool): Use low-speed mode. Defaults to False.
            logfile (Optional[str]): The path to the log file. If provided, the log will
                be written to this file. Defaults to None.

        Raises:
            SIReaderException: If no SI Reader is found.
        """
        self._serial: Optional[Serial] = None  # Serial port object
        self._debug: bool = debug
        self.proto_config: Optional[dict] = None
        self._station_code: Optional[int] = None
        self._serno: int = 0  # Serial number of station
        self.direct: bool = True  # Direct or remote mode
        self._noconnect: bool = noconnect
        self._lowspeed: bool = lowspeed

        # TODO: refactor logging to file
        if logfile is not None:
            self._logfile = open(logfile, "ab")
        else:
            self._logfile = None
        self.sysval: str = (
            ""  # The most recently read station configuration information
        )

        errors = ""
        if port is not None:
            self._connect_reader(port)
            return
        else:
            scan_ports = self.guess_serial_ports()

            if len(scan_ports) == 0:
                errors = "no serial ports found"

            for port in scan_ports:
                try:
                    print("Trying " + port)
                    self._connect_reader(port)
                    return
                except (SIReaderException, SIReaderTimeout) as msg:
                    errors = "%sport: %s: %s\n" % (errors, port, msg)
                    pass

        raise SIReaderException("No SI Reader found. Possible reasons: %s" % errors)

    @staticmethod
    def guess_serial_ports(ttyS: bool = False) -> List[str]:
        """
        Look for a COM port that might be connected to a Sportident station.

        Args:
            ttyS (bool): Flag indicating whether to include ttyS ports on Linux. Default is False.

        Returns:
            List[str]: A list of found COM ports that might be connected to a Sportident station.
        """
        found: List[str] = []
        if sys.platform.startswith("linux"):
            found = [
                os.path.join("/dev", f)
                for f in os.listdir("/dev")
                if re.match("ttyS.*|ttyUSB.*" if ttyS else "ttyUSB.*", f)
            ]
        elif sys.platform.startswith("darwin"):
            with os.scandir("/dev") as it:
                for entry in it:
                    # assume that silabs.com CP210x USB to UART bridge is used
                    if entry.name.startswith("tty.SLAB"):
                        found.append(os.path.join("/dev", entry.name))
        elif sys.platform.startswith("win"):
            # Rank ports based on some kind of criteria of how
            # likely they are to be the correct port.
            portname = False
            ports = list(serial.tools.list_ports.comports())
            ranked_ports = []
            for p in ports:
                portname = p[0]
                portname1 = p[1]
                portname2 = p[2]
                points = 0
                if portname == "COM1":
                    # COM1 is often not accessible on modern computers
                    points -= 1
                if "sportident" in portname1.lower():
                    points += 10
                if "acpi" in portname2.lower():
                    points -= 5
                ranked_ports.append([points, portname, portname1, portname2])

            # Sort on ranking
            ranked_ports.sort(key=lambda portinfo: -portinfo[0])
            # Try out the ports in the order they are ranked
            for portinfo in ranked_ports:
                try:
                    with Serial(portinfo[1]) as s:
                        found.append(s.portstr)
                except SerialException:
                    pass
        else:
            raise SIReaderException("Unsupported OS: %s" % sys.platform)

        return found

    @classmethod
    def scan_stations(cls, lowspeed: bool = False) -> List[Tuple[str, int]]:
        """Scans all the possible serial ports and tries to find a SportIdent station.

        Args:
            lowspeed (bool, optional): Flag indicating whether to use low-speed mode. Defaults to False.

        Returns:
            list: A list of tuples containing the found serial ports and their corresponding station codes.
        """

        found = []

        def _run(port: str):
            si = cls(port=port, debug=True, lowspeed=lowspeed)
            stationCode = si.get_station_code()
            found.append((port, stationCode))
            si.disconnect()

        threads = []
        # Search in parallel
        for port in cls.guess_serial_ports():
            # TODO: don't use threading, use asyncio
            t = threading.Thread(target=_run, args=(port,))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        return found

    def flush(self):
        """
        Flushes the input and output buffers of the serial connection.
        """
        self._serial.flushInput()
        self._serial.flushOutput()

    def set_extended_protocol(self, extended: bool = True):
        """Configure extended protocol mode of SI station.

        Args:
            extended (bool, optional): Set extended protocol if True, legacy protocol if False.
        """
        config = self.proto_config.copy()
        config["ext_proto"] = extended
        self._set_proto_config(config)

    def set_autosend(self, autosend: bool = True):
        """Set si station into autosend mode.

        Args:
            autosend (bool, optional): Set autosend mode if True, unset otherwise.
        """
        config = self.proto_config.copy()
        config["auto_send"] = autosend
        config["handshake"] = not autosend
        self._set_proto_config(config)

    def set_operating_mode(
        self,
        mode: Literal[
            "M_CONTROL", "M_START", "M_FINISH", "M_READOUT", "M_CLEAR", "M_CHECK"
        ],
    ):
        """Set SI station operating mode.

        Args:
            mode (Literal["M_CONTROL", "M_START", "M_FINISH", "M_READOUT", "M_CLEAR", "M_CHECK"]): The operating mode to set.

        Raises:
            SIReaderException: If the mode is not supported.
        """
        if not mode in SIReader.SUPPORTED_MODES:
            raise SIReaderException("Unsupported mode '%i'!" % mode)
        try:
            self._send_command(SIReader.C_SET_SYS_VAL, SIReader.O_MODE + int2byte(mode))
        finally:
            self._update_proto_config()

    def set_station_code(self, code: int):
        """Sets the SI station control code.

        Args:
            code (int): The control code (1-1023).

        Raises:
            SIReaderException: If the control code is invalid.
        """
        if code < 1 or code > 1023:
            raise SIReaderException(
                "Invalid control code: '%i'! Supported code range: 1-1023." % code
            )
        # lower byte of control code
        code_low = int2byte(code & 0xFF)
        # high byte of control code, only the first 2 bits are used, the rest are set to 1
        code_high = int2byte((code >> 2) | 0b00111111)
        try:
            self._send_command(
                SIReader.C_SET_SYS_VAL, SIReader.O_STATION_CODE + code_low + code_high
            )
        finally:
            self._update_proto_config()

    def set_baud_rate(self, baud_rate: Literal[4800, 38400]):
        """Set the baudrate of the direct or remote station.

        Args:
            baud_rate (Literal[4800, 38400]): The baudrate to set. Must be either 4800 or 38400.

        Raises:
            SIReaderException: If an unsupported baud rate is provided.
        """
        if baud_rate not in (4800, 38400):
            raise SIReaderException("Unsupported baud rate '%i'!" % baud_rate)
        baud_rate_identifier = b"\x00" if baud_rate == 4800 else b"\x01"
        self._send_command(SIReader.C_SET_BAUD, baud_rate_identifier)
        self._serial.baudrate = baud_rate

    def set_baud_rate_4800(self):
        """Set the baudrate to 4800"""
        self.set_baud_rate(4800)

    def set_baud_rate_38400(self):
        """Set the baudrate to 38400"""
        self.set_baud_rate(38400)

    def refresh_sysval(self):
        """Read the entire station configuration information (SYS_VAL) and store in the object
        so that the sysval_ functions can return good information.
        """
        self.sysval = self._send_command(SIReader.C_GET_SYS_VAL, b"\x00\x80")[1]

    def save_sys_val(self, filename=None):
        """Save the station configuration data (SYS_VAL) to a CSV file.
        Two values per row, offset and byte, in decimal format.
        If no filename is given, a name is created consisting of the code of the station
        and the current date and time.
        @param filename: optional name of CSV file
        @return:         The name of the CSV file
        """
        if len(self.sysval) < 0x80:
            self.refresh_sysval()
        code = self.sysval_code()
        datestr = datetime.now().strftime("%Y-%m-%d_%H.%M.%S")
        if filename is None:
            filename = str(code) + "_" + datestr + "_sysval.csv"
        with open(filename, "w", newline="") as csvfile:
            csvwriter = csv.writer(
                csvfile, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL
            )
            header = ["Offset", "Value"]
            csvwriter.writerow(header)
            offs = 0
            for byte in self.sysval[1:]:
                csvwriter.writerow([offs, byte])
                offs += 1
            return filename
        return ""

    def sysval_serno(self):
        """Return the station serial number from the most recent reading of SYS_VAL.
        @return : station serial number as an integer
        """
        if len(self.sysval) < 0x80:
            self.refresh_sysval()
        return SIReader._to_int(
            SIReader._extract_sysval(self.sysval, SIReader.O_SERIAL_NO, 4)
        )

    def sysval_fwver(self):
        """Return the station firmware version from the most recent reading of SYS_VAL.
        @return : firmware station serial number as a 3-character string
        """
        if len(self.sysval) < 0x80:
            self.refresh_sysval()
        return SIReader._extract_sysval(self.sysval, SIReader.O_FIRMWARE, 3).decode(
            "ascii"
        )

    def sysval_model_id(self):
        """Return the station model id from the most recent reading of SYS_VAL.
        @return : model id, an integer
        """
        if len(self.sysval) < 0x80:
            self.refresh_sysval()
        return SIReader._to_int(
            SIReader._extract_sysval(self.sysval, SIReader.O_MODEL_ID, 2)
        )

    def sysval_model_str(self):
        """Return the station model (as a string) from the most recent reading of SYS_VAL.
        @return : model, a string
        """
        model_id = self.sysval_model_id()
        model_id_recognized = model_id in SIReader.MODEL2NAME
        return (
            SIReader.MODEL2NAME[model_id]
            if model_id_recognized
            else "0x%04x" % model_id
        )

    def sysval_build_date(self):
        """Return the station build date from the most recent reading of SYS_VAL.
        @return : build-date as a string YYYY-MM-DD
        """
        if len(self.sysval) < 0x80:
            self.refresh_sysval()
        date_str = SIReader._extract_sysval(self.sysval, SIReader.O_BUILD_DATE, 3)
        date_str = "20%02d-%02d-%02d" % (date_str[0], date_str[1], date_str[2])
        return date_str

    def sysval_battery_date(self):
        """Return the station battery date from the most recent reading of SYS_VAL.
        @return : build-date as a string YYYY-MM-DD
        """
        if len(self.sysval) < 0x80:
            self.refresh_sysval()
        date_str = SIReader._extract_sysval(self.sysval, SIReader.O_BAT_DATE, 3)
        date_str = "20%02d-%02d-%02d" % (date_str[0], date_str[1], date_str[2])
        return date_str

    def sysval_mem_size(self):
        """Return the station's memory size from the most recent reading of SYS_VAL.
        @return : station's memory size in kB
        """
        if len(self.sysval) < 0x80:
            self.refresh_sysval()
        return SIReader._to_int(
            SIReader._extract_sysval(self.sysval, SIReader.O_MEM_SIZE, 1)
        )

    def sysval_volt(self):
        """Return the station voltage from the most recent reading of SYS_VAL.
        @return : voltage, a float, V
        """
        if len(self.sysval) < 0x80:
            self.refresh_sysval()
        return (
            SIReader._to_int(
                SIReader._extract_sysval(self.sysval, SIReader.O_BAT_VOLT, 2)
            )
            * 5.0
        ) / 65536.0

    def sysval_battery_capacity(self):
        """Return the station's battery capacity from the most recent reading of SYS_VAL.
        @return : capacity, a float, mAh
        """
        if len(self.sysval) < 0x80:
            self.refresh_sysval()
        return (
            SIReader._to_int(
                SIReader._extract_sysval(self.sysval, SIReader.O_BAT_CAP, 2)
            )
            * 16.0
        ) / 225.0

    def sysval_used_battery(self):
        """Return the station's used battery capacity from the most recent reading of SYS_VAL.
        @return : used capacity, a float, %
        """
        if len(self.sysval) < 0x80:
            self.refresh_sysval()
        return (
            SIReader._to_int(
                SIReader._extract_sysval(self.sysval, SIReader.O_USED_BAT_CAP, 3)
            )
            * 2.778e-5
        )

    def sysval_mode_str(self):
        """Return the station operating mode from the most recent reading of SYS_VAL.
        @return : mode, a string
        """
        if len(self.sysval) < 0x80:
            self.refresh_sysval()
        mode = SIReader._to_int(
            SIReader._extract_sysval(self.sysval, SIReader.O_MODE, 1)
        )
        if mode in SIReader.MODE2NAME:
            mode_str = SIReader.MODE2NAME[mode]
        else:
            mode_str = "0x%02x" % mode
        return mode_str

    def sysval_code(self):
        """Return the station code from the most recent reading of SYS_VAL.
        @return : code, 1-1023
        """
        if len(self.sysval) < 0x80:
            self.refresh_sysval()
        code_low = SIReader._to_int(
            SIReader._extract_sysval(self.sysval, SIReader.O_STATION_CODE, 1)
        )
        # Also contains high bits of code
        feedback = SIReader._to_int(
            SIReader._extract_sysval(self.sysval, SIReader.O_FEEDBACK, 1)
        )
        self._station_code = code_low + ((feedback & 0b11000000) << 2)
        return self._station_code

    def sysval_feedback(self):
        """Return the station feedback byte from the most recent reading of SYS_VAL.
        @return : feedback, an integer, 0-255
        """
        if len(self.sysval) < 0x80:
            self.refresh_sysval()
        return SIReader._to_int(
            SIReader._extract_sysval(self.sysval, SIReader.O_FEEDBACK, 1)
        )

    def sysval_192_punches(self):
        """Return the station's setting regarding 192 punches for SI card 6
        from the most recent reading of SYS_VAL.
        @return : True if it is set, False if not, a byte is the value is unexpected
        """
        if len(self.sysval) < 0x80:
            self.refresh_sysval()
        si6_192 = SIReader._to_int(
            SIReader._extract_sysval(self.sysval, SIReader.O_SI6_CB, 1)
        )
        if si6_192 == 0 or si6_192 == 0xC1:
            return False
        if si6_192 == 0x08 or si6_192 == 0xFF:
            return True
        return si6_192

    def sysval_protocol(self):
        """Return the station protocol byte from the most recent reading of SYS_VAL.
        @return : protocol, an integer, 0-255
        """
        if len(self.sysval) < 0x80:
            self.refresh_sysval()
        return SIReader._to_int(
            SIReader._extract_sysval(self.sysval, SIReader.O_PROTO, 1)
        )

    def sysval_active_time(self):
        """Return the station active time from the most recent reading of SYS_VAL.
        @return : active time, an integer 0-5759 minutes
        """
        if len(self.sysval) < 0x80:
            self.refresh_sysval()
        return SIReader._to_int(
            SIReader._extract_sysval(self.sysval, SIReader.O_ACTIVE_TIME, 2)
        )

    def set_feedback(self, audible=True, optical=True):
        """Set the optical and audible feedback of the station.
        Default is to turn them both on.
        @param audible : Boolean (optional, default True)
        @param optical : Boolean (optional, default True)
        """
        if len(self.sysval) < 0x80:
            self.refresh_sysval()
        feedback = SIReader._to_int(
            SIReader._extract_sysval(self.sysval, SIReader.O_FEEDBACK, 1)
        )
        if optical:
            feedback |= 0b00000001
        else:
            feedback &= ~0b00000001
        if audible:
            feedback |= 0b00000100
        else:
            feedback &= ~0b00000100
        self._send_command(
            SIReader.C_SET_SYS_VAL, SIReader.O_FEEDBACK + int2byte(feedback)
        )

    def set_active_time(self, time):
        """Set the active time.
        @param time : minutes, 0-5759
        """
        if len(self.sysval) < 0x80:
            self.refresh_sysval()
        time_barr = SIReader._to_str(time, 2)
        self._send_command(SIReader.C_SET_SYS_VAL, SIReader.O_ACTIVE_TIME + time_barr)

    def set_si6_192(self, enable=False):
        """Set whether the station shall support SI card 6 with 192 punches.
        @param enable : Boolean, default is False
        """
        if enable:
            self._send_command(SIReader.C_SET_SYS_VAL, SIReader.O_SI6_CB + b"\xFF")
        else:
            self._send_command(SIReader.C_SET_SYS_VAL, SIReader.O_SI6_CB + b"\xC1")

    def get_station_code(self):
        """Get si station control code.
        @return : control code (1-1023)
        """
        return self._station_code

    def get_time(self):
        """Read out station's internal time.
        @return: datetime
        """
        bintime = self._send_command(SIReader.C_GET_TIME, b"")[1]
        year = byte2int(bintime[0]) + 2000
        month = byte2int(bintime[1])
        day = byte2int(bintime[2])
        am_pm = byte2int(bintime[3]) & 0b1
        second = SIReader._to_int(bintime[4:6])
        hour = am_pm * 12 + second // 3600
        second %= 3600
        minute = second // 60
        second %= 60
        ms = int(round(byte2int(bintime[6]) / 256.0 * 1000000))
        try:
            return datetime(year, month, day, hour, minute, second, ms)
        except ValueError:
            # return None if the time reported by the station is impossible
            return None

    def set_time(self, time):
        """Set si station internal time.
        @param time: time as a python datetime object.
        """
        bintime = (
            SIReader._to_str(int(time.strftime("%y")), 1)
            + SIReader._to_str(time.month, 1)
            + SIReader._to_str(time.day, 1)
            + SIReader._to_str(((time.isoweekday() % 7) << 1) + time.hour // 12, 1)
            + SIReader._to_str(
                (time.hour % 12) * 3600 + time.minute * 60 + time.second, 2
            )
            + SIReader._to_str(int(round(time.microsecond / 1000000.0 * 256)), 1)
        )

        self._send_command(SIReader.C_SET_TIME, bintime)

    def beep(self, count=1):
        """Beep and blink control station. This even works if now sicard is
        inserted into the station.
        @param count: Count of beeps
        """
        self._send_command(SIReader.C_BEEP, int2byte(count))

    def set_direct(self):
        """Set the station to direct (master) mode."""
        self._send_command(SIReader.C_SET_MS, SIReader.P_MS_DIRECT)
        self.direct = True

    def set_remote(self):
        """Set the station to remote (slave, indirect) mode."""
        self._send_command(SIReader.C_SET_MS, SIReader.P_MS_INDIRECT)
        self.direct = False

    def read_backup(self, progress=0):
        """Read out the entire backup memory of a station configured as
        control, check, clear, start or finish.
        Before calling this function: set the station in direct or remote mode
        depending on whether the master or slave should be read.
        The station connected to the computer has to be in extended protocol mode.
        The remote station can be in either extended or legacy mode.
        @param progress: Set this to 1 to have the function print out
                         progress indications.
        @return:         A list of tuples:  (date, cardnr, error)
                         'date' is a datetime object with the punch time
                         'cardnr' is an int with the card number
                         'error' is an empty string if there was
                         no error in the punch and a string like "ErrA"
                         etc if there was an error.
                         In case of error, the 'date' field is set to
                         midnight or noon of the actual date.
        """

        # Check which protocol is in use and which mode the station is in
        self._update_proto_config()
        if not self.proto_config["mode"] in SIReader.SUPPORTED_READ_BACKUP_MODES:
            raise SIReaderException(
                "Station is in unsupported mode: %s"
                % SIReader.MODE2NAME[self.proto_config["mode"]]
            )

        # Read out backup memory pointers
        ret = self._send_command(SIReader.C_GET_SYS_VAL, b"\x00\x80")[1]

        offs1 = byte2int(SIReader.O_BACKUP_PTR_HI) + 1
        offs2 = byte2int(SIReader.O_BACKUP_PTR_LO) + 1
        end_ptr = SIReader._to_int(ret[offs1 : offs1 + 2] + ret[offs2 : offs2 + 2])

        # Read out entire used backup memory.
        # It seems like we can only read out 0x80 bytes at a time, so we might need
        # to divide the read into several commands.
        bakmem = b""
        read_ptr = 0x100  # This is where reading always seems to start
        while read_ptr < end_ptr:
            read_ptr_bytes = (
                int2byte(read_ptr >> 16)
                + int2byte((read_ptr >> 8) & 0xFF)
                + int2byte(read_ptr & 0xFF)
            )
            byte_cnt = b"\x80"
            if end_ptr - read_ptr < 0x80:
                byte_cnt = int2byte(end_ptr - read_ptr)
            ret = self._send_command(SIReader.C_GET_BACKUP, read_ptr_bytes + byte_cnt)[
                1
            ]
            if progress > 0:
                print(".", end="")
                sys.stdout.flush()
            if self.proto_config["ext_proto"]:
                # Extended protocol
                bakmem += ret[SIReader.BUX_FIRST + 1 :]
                step = SIReader.BUX_SIZE
            else:
                # Legacy protocol
                bakmem += ret[SIReader.BUL_FIRST + 1 :]
                step = SIReader.BUL_SIZE
            read_ptr += byte2int(byte_cnt)

        # Gather some time-information to help guessing what dates
        # punches from the basic protocol belongs to.
        now_datetime = datetime.now()
        now_weekday = now_datetime.weekday()
        secs_since_midnight = (
            now_datetime
            - now_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
        ).total_seconds()
        # Loop over punch data
        res = []
        ii = 0
        while ii < len(bakmem):
            punch = bakmem[ii : ii + step]
            err = ""
            secs = 0
            us = 0
            if self.proto_config["ext_proto"]:
                # Extended protocol
                cardnr_bytes = b"\x00" + punch[SIReader.BUX_CN : SIReader.BUX_CN + 3]
                cardnr = SIReader._decode_cardnr(cardnr_bytes)
                year = 2000 + (punch[SIReader.BUX_YM] >> 2)
                month = ((punch[SIReader.BUX_YM] & 0x3) << 2) + (
                    punch[SIReader.BUX_MDAP] >> 6
                )
                day = (punch[SIReader.BUX_MDAP] & 0x3F) >> 1
                ampm = punch[SIReader.BUX_MDAP] & 0x01
                if byte2int(punch[SIReader.BUX_SECS]) >= 0xF0:
                    # Error code
                    err = "Err%X" % byte2int(punch[SIReader.BUX_SECS] & 0xF)
                else:
                    secs = SIReader._to_int(
                        punch[SIReader.BUX_SECS : SIReader.BUX_SECS + 2]
                    )
                    us = (
                        1e6
                        * SIReader._to_int(punch[SIReader.BUX_MS : SIReader.BUX_MS + 1])
                        / 256
                    )
                if month == 0:
                    # This is weird, but happened during testing. Corrupted memory?
                    month += 12
                    year -= 1
                    err += "ErrDate"
                if month > 12:
                    # This should not happen, unless the backup memory is corrupt.
                    month -= 12
                    year += 1
                    err += "ErrDate"
                secs += 12 * 3600 * ampm
                punch_datetime = datetime(year, month, day) + timedelta(
                    seconds=secs, microseconds=us
                )
            else:
                # Legacy protocol
                cardnr_bytes = (
                    "\x00"
                    + punch[SIReader.BUL_CNS : SIReader.BUL_CNS + 1]
                    + punch[SIReader.BUL_CN : SIReader.BUL_CN + 2]
                )
                cardnr = SIReader._decode_cardnr(cardnr_bytes)
                weekday = (
                    (punch[SIReader.BUL_PTD] & 0x0E) >> 1 - 1
                ) % 7  # Monday = 0 etc
                ampm = punch[SIReader.BUL_PTD] & 0x01
                if byte2int(punch[SIReader.BUL_SECS]) >= 0xF0:
                    # Error code
                    err = "Err%X" % byte2int(punch[SIReader.BUL_SECS] & 0xF)
                else:
                    secs = SIReader._to_int(
                        punch[SIReader.BUL_SECS : SIReader.BUL_SECS + 2]
                    )
                secs += 12 * 3600 * ampm
                # In legacy protocol, we really only know what weekday the punch took place,
                # but in order to be able to return a convenient datetime, we assume it took
                # place within the last seven days and provide a full datetime
                # based on this assumption.
                if (
                    weekday * 24 * 3600 + secs
                    < now_weekday * 24 * 3600 + secs_since_midnight + 3600
                ):
                    # Punch probably took place earlier this week.
                    # The added 3600 seconds above is to handle the case if the computer
                    # and station are not in sync.
                    day_offset = now_weekday - weekday
                else:
                    # Punch probably took place last week
                    day_offset = now_weekday - weekday + 7
                punch_datetime = now_datetime.replace(
                    hour=0, minute=0, second=0, microsecond=0
                ) + timedelta(seconds=secs, days=day_offset)
            res.append((punch_datetime, cardnr, err))
            ii += step
        if progress > 0:
            print("")
        return res

    def write_backup_csv(
        self, data, code=0, serno=0, mode="", filename=None, readtime=None
    ):
        """Write the backup data read from a station's backup memory to
        a CSV file of the same format as created by Sportident Config+.
        @param data:     the list of tuples with backup data
                         returned by read_backup()
        @param code:     the control code number. Default is the code of
                         the current station.
        @param serno:    the station's serial number. Default the
                         serial number of the current station.
        @param mode:     the station's operating mode as a string.
                         Allowed values are 'Control', 'Check',
                         'Start', 'Clear', 'Finish'.
                         Default is the mode of the current station.
        @param filename: the filename to use. If none is given, one is constructed
                         with the format: <code>_<mode>_<serno>.csv
        @param readtime: A datetime object with the time when the station was read.
                         Default is to use the current time.
        @return:         The name of the CSV file.
        """
        if code == 0:
            code = self._station_code
        codestr = str(code)
        if serno == 0:
            serno = self._serno
        if mode == "":
            if self.proto_config["mode"] == SIReader.M_CONTROL:
                mode = "Control"
            elif self.proto_config["mode"] == SIReader.M_START:
                mode = "Start"
            elif self.proto_config["mode"] == SIReader.M_FINISH:
                mode = "Finsih"
            elif self.proto_config["mode"] == SIReader.M_CLEAR_OLD:
                mode = "Clear"
            elif self.proto_config["mode"] == SIReader.M_CLEAR:
                mode = "Clear"
            elif self.proto_config["mode"] == SIReader.M_CHECK:
                mode = "Check"
            else:
                mode = "???"

        if filename is None:
            filename = codestr + "_" + mode + "_" + str(serno) + ".csv"
        with open(filename, "w", newline="") as csvfile:
            csvwriter = csv.writer(
                csvfile, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL
            )
            header = [
                "No",
                "Read on",
                "SIID",
                "Control time",
                "Battery voltage",
                "Serial number",
                "Code number",
                "DayOfWeek",
                "Punch DateTime",
                "Operating mode",
                "SIAC number",
                "SIAC Count",
                "SIAC radio mode",
                "SIAC is battery low",
                "SIAC is card full",
                "SIAC beacon mode",
                "SIAC is gate mode",
                "",
            ]
            days = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]
            csvwriter.writerow(header)
            if readtime is None:
                readtime = datetime.now()
            readtimestr = readtime.isoformat(timespec="seconds", sep=" ")

            ii = 1
            for punchdata in data:
                date = punchdata[0]
                if date.microsecond == 0:
                    # Make sure microseconds are always printed
                    date.replace(microsecond=1)
                cardno = punchdata[1]
                err = punchdata[2]
                datestr = date.isoformat(sep="$")[0:23]
                datestr = datestr.replace("$", "   ")

                if err == "":
                    # No error, normal case
                    dayno = int(date.strftime("%w"))  # Day of week, Sun = 0
                    dayname = days[dayno]
                    timestr = datestr[13:]
                else:
                    # Error
                    datestr = datestr[0:13] + err
                    dayname = ""
                    timestr = "00:00:00"
                row = [
                    ii,
                    readtimestr,
                    cardno,
                    datestr,
                    "",
                    "",
                    codestr,
                    dayname,
                    timestr,
                    mode,
                    "0",
                    "1",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
                csvwriter.writerow(row)
                ii += 1
        return filename

    def erase_backup(self):
        """Erase the backup memory of the station."""
        self._send_command(SIReader.C_ERASE_BACKUP, b"")

    def poweroff(self):
        """Switch off the control station."""
        self._send_command(SIReader.C_OFF, b"")

    def disconnect(self):
        """Close the serial port an disconnect from the station."""
        self._serial.close()

    def reconnect(self):
        """Close the serial port and reopen again."""
        self.disconnect()
        self._connect_reader(self._serial.port)

    def _connect_reader(self, port):
        """Connect to SI Reader.
        @param port: serial port
        """
        baudrate = 4800 if self._noconnect or self._lowspeed else 38400
        try:
            self._serial = Serial(port, baudrate=baudrate, timeout=2)
        except (SerialException, OSError):
            raise SIReaderException("Could not open port '%s'" % port)

        # flush possibly available input
        try:
            self.flush()
        except (SerialException, OSError):
            # This happens if the serial port is not ready for
            # whatever reason (eg. there is no real device behind this device node).
            raise SIReaderException("Could not flush port '%s'" % port)

        if not self._noconnect:
            try:
                # try at max baud rate, extended protocol
                self._send_command(SIReader.C_SET_MS, SIReader.P_MS_DIRECT)
            except (SIReaderException, SIReaderTimeout):
                if self._serial.baudrate == 4800:
                    raise
                else:
                    # try at 4800 baud rate this time
                    try:
                        self._serial.baudrate = 4800
                    except (SerialException, OSError) as msg:
                        raise SIReaderException(
                            "Could not set port speed to 4800: %s" % msg
                        )
                    try:
                        self._send_command(SIReader.C_SET_MS, SIReader.P_MS_DIRECT)
                    except SIReaderException as msg:
                        raise SIReaderException(
                            "This module only works with BSM7/8 stations: %s" % msg
                        )

        self.port = port
        self.baudrate = self._serial.baudrate
        self._update_proto_config()
        self.name = self._serial.name

    def _update_proto_config(self):
        self.proto_config = {}
        if self._noconnect:
            self.proto_config["ext_proto"] = True
            self.proto_config["auto_send"] = True
            self.proto_config["handshake"] = False
            self.proto_config["pw_access"] = False
            self.proto_config["punch_read"] = False
            self.proto_config["mode"] = 2
            self._serno = 0
            self._station_code = 0
        else:
            # Read protocol configuration
            sysval = self._send_command(SIReader.C_GET_SYS_VAL, b"\x00\x80")[1]
            config_byte = byte2int(
                SIReader._extract_sysval(sysval, SIReader.O_PROTO, 1)
            )
            self.proto_config["ext_proto"] = config_byte & (1 << 0) != 0
            self.proto_config["auto_send"] = config_byte & (1 << 1) != 0
            self.proto_config["handshake"] = config_byte & (1 << 2) != 0
            self.proto_config["pw_access"] = config_byte & (1 << 4) != 0
            self.proto_config["punch_read"] = config_byte & (1 << 7) != 0
            mode_byte = byte2int(SIReader._extract_sysval(sysval, SIReader.O_MODE, 1))
            self.proto_config["mode"] = mode_byte
            serno = SIReader._to_int(
                SIReader._extract_sysval(sysval, SIReader.O_SERIAL_NO, 4)
            )
            self._serno = serno
            # self._station_code is updated in the call above to _send_command()

        return self.proto_config

    def _set_proto_config(self, config):
        try:
            config_byte = int2byte(
                (config["ext_proto"] << 0)
                | (config["auto_send"] << 1)
                | (config["handshake"] << 2)
                | (config["pw_access"] << 4)
                | (config["punch_read"] << 7)
            )
            self._send_command(SIReader.C_SET_SYS_VAL, SIReader.O_PROTO + config_byte)
        finally:
            self._update_proto_config()

    def __del__(self):
        """
        Closes the serial connection and log file (if open) when the object is deleted.
        """
        if self._serial is not None:
            self._serial.close()
        if self._logfile is not None:
            self._logfile.close()

    @staticmethod
    def _to_int(s):
        """Computes the integer value of a raw byte string."""
        value = 0
        for offset, c in enumerate(iterbytes(s[::-1])):
            value += c << offset * 8
        return value

    @staticmethod
    def _to_str(i, len):
        """
        @param i:   Integer to convert into str
        @param len: Length of the return value. If i does not fit OverflowError is raised.
        @return:    string representation of i (MSB first)
        """
        if PY3:
            return i.to_bytes(len, "big")
        if i >> len * 8 != 0:
            raise OverflowError("%i too big to convert to %i bytes" % (i, len))
        string = ""
        for offset in range(len - 1, -1, -1):
            string += int2byte((i >> offset * 8) & 0xFF)
        return string

    @staticmethod
    def _crc(s):
        """Compute the crc checksum of value. This implementation is
        a reimplementation of the Java function in the SI Programmers
        manual examples."""

        def twochars(s):
            """generator that splits a string into parts of two chars"""
            if len(s) == 0:
                # immediately stop on empty string
                return

            # add 0 to the string and make it even length
            if len(s) % 2 == 0:
                s += b"\x00\x00"
            else:
                s += b"\x00"
            for i in range(0, len(s), 2):
                yield s[i : i + 2]

        if len(s) < 1:
            # return value for 1 or no data byte is 0
            return b"\x00\x00"

        crc = SIReader._to_int(s[0:2])

        for c in twochars(s[2:]):
            val = SIReader._to_int(c)

            for j in range(16):
                if (crc & SIReader.CRC_BITF) != 0:
                    crc <<= 1

                    if (val & SIReader.CRC_BITF) != 0:
                        crc += 1  # rotate carry

                    crc ^= SIReader.CRC_POLYNOM
                else:
                    crc <<= 1

                    if (val & SIReader.CRC_BITF) != 0:
                        crc += 1  # rotate carry

                val <<= 1

        # truncate to 16 bit and convert to char
        crc &= 0xFFFF
        return int2byte(crc >> 8) + int2byte(crc & 0xFF)

    @staticmethod
    def _crc_check(s, crc):
        return SIReader._crc(s) == crc

    @staticmethod
    def _decode_cardnr(number):
        """Decodes a 4 byte cardnr to an int. SI-Card numbering is a bit odd:
        SI-Card 5:
           - byte 0:   always 0 (not stored on the card)
           - byte 1:   card series (stored on the card as CNS)
           - byte 2,3: card number
           - printed:  100'000*CNS + card number
           - nr range: 1-65'000 + 200'001-265'000 + 300'001-365'000 + 400'001-465'000
        SI-Card 6/6*/8/9/10/11/pCard/tCard/fCard/SIAC1:
           - byte 0:   card series (SI6:00, SI9:01, SI8:02, pCard:04, tCard:06, fCard:0E, SI10+SI11+SIAC1:0F)
           - byte 1-3: card number
           - printed:  only card number
           - nr range:
               - SI6: 500'000-999'999 + 2'003'000-2'003'400 (WM2003) + 16'711'680-16'777'215 (SI6*)
               - SI9: 1'000'000-1'999'999, SI8: 2'000'000-2'999'999
               - pCard: 4'000'000-4'999'999, tCard: 6'000'000-6'999'999
               - SI10: 7'000'000-7'999'999, SIAC1: 8'000'000-8'999'999
               - SI11: 9'000'000-9'999'999, fCard: 14'000'000-14'999'999

        The card nr ranges guarantee that no ambigous values are possible
        (500'000 = 0x07A120 > 0x04FFFF = 465'535 = highest technically possible value on a SI5)
        """

        if number[0:1] != b"\x00":
            raise SIReaderException("Unknown card series")

        nr = SIReader._to_int(number[1:4])
        if nr < 500000:
            # SI5 card
            ret = SIReader._to_int(number[2:4])
            if byte2int(number[1]) < 2:
                # Card series 0 and 1 do not have the 0/1 printed on the card
                return ret
            else:
                return byte2int(number[1]) * 100000 + ret
        else:
            # SI6/8/9
            return nr

    @staticmethod
    def _decode_time(raw_time, raw_ptd=None, reftime=None):
        """Decodes a raw time value read from an si card into a datetime object.
        The returned time is the nearest time matching the data before reftime."""

        if raw_time == SIReader.TIME_RESET:
            return None

        if reftime is None:
            # add two hours as a safety marging for cases where the
            # machine time runs a bit behind the station's time.
            reftime = datetime.now() + timedelta(hours=2)

        # punchtime is in the range 0h-12h!
        punchtime = timedelta(seconds=SIReader._to_int(raw_time))

        # Documentation of the PTD byte from SportIdent
        # bit 0 - am/pm
        # bit 3...1 - day of week, 000 = Sunday, 110 = Saturday
        # bit 5...4 - week counter 0...3, relative
        # bit 7...6 - control station code number high
        # (...511)
        # week counter is not used!

        if raw_ptd is not None:
            ptd = byte2int(raw_ptd)

            # get info about AM(0) or PM(1)
            # and adjust punchtime in case of PM
            if (ptd & 0b00000001) == 0b1:
                punchtime = punchtime + timedelta(hours=12)

            # extract day of week and convert to Mon = 0, Tue = 1 ... as
            # datetime.weekday has Mon = 0, Sun = 6 the modulo operation
            # takes care of underflows (Sun = -1)
            dow = (((ptd & 0b00001110) >> 1) - 1) % 7

            # subtract a whole week if the dow week is the same but the punchtime
            # is later on the same day
            if reftime.weekday() == dow and punchtime > timedelta(
                hours=reftime.hour, minutes=reftime.minute, seconds=reftime.second
            ):
                reftime -= timedelta(days=7)
            else:
                # adjust reftime according to weekday information
                reftime -= timedelta(days=(reftime.weekday() - dow) % 7)

            ref_day = reftime.replace(
                hour=0, minute=0, second=0, microsecond=0, tzinfo=None
            )
            return ref_day + punchtime

        # No PTD byte available, we have to rely on guessing the closest 12h time

        ref_day = reftime.replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=None
        )
        ref_hour = reftime - ref_day
        t_noon = timedelta(hours=12)

        if ref_hour < t_noon:
            # reference time is before noon
            if punchtime < ref_hour:
                # t is between 00:00 and t_ref
                return ref_day + punchtime
            else:
                # t is afternoon the day before
                return ref_day - t_noon + punchtime
        else:
            # reference is after noon
            if punchtime < ref_hour - t_noon:
                # t is between noon and t_ref
                return ref_day + t_noon + punchtime
            else:
                # t is in the late morning
                return ref_day + punchtime

    @staticmethod
    def _decode_station_code(raw_code, raw_ptd=None):
        """Decodes the station code read from an si card.
        For cards newer than SI5, there are possibly two extra bits in the ptd byte,
        allowing codes up to 1023 (although in practice these are rarely used by
        organizers as it would preclude the use of SI5 cards)."""
        if raw_ptd is not None:
            return ((raw_ptd & 0xC0) << 2) + raw_code
        else:
            return raw_code

    @staticmethod
    def _append_punch(list, station, timedata, ptd, reftime):
        time = SIReader._decode_time(timedata, ptd, reftime)
        if time is not None:
            list.append((station, time))

    @staticmethod
    def _decode_carddata(data, card_type, reftime=None):
        """Decodes a data record read from an SI Card."""

        ret = {}
        card = SIReader.CARD[card_type]

        # the slicing of data is necessary for Python 3 to get a bytes object instead
        # of an int
        ret["card_number"] = SIReader._decode_cardnr(
            b"\x00"
            + data[card["CN2"] : card["CN2"] + 1]
            + data[card["CN1"] : card["CN1"] + 1]
            + data[card["CN0"] : card["CN0"] + 1]
        )

        time_day = data[card["STD"]] if card["STD"] else None
        code = data[card["SN"]] if card["SN"] is not None else None
        ret["start"] = SIReader._decode_time(
            data[card["ST"] : card["ST"] + 2], time_day, reftime
        )
        ret["start_code"] = SIReader._decode_station_code(code, time_day)

        time_day = data[card["FTD"]] if card["FTD"] else None
        code = data[card["FN"]] if card["FN"] is not None else None
        ret["finish"] = SIReader._decode_time(
            data[card["FT"] : card["FT"] + 2], time_day, reftime
        )
        ret["finish_code"] = SIReader._decode_station_code(code, time_day)

        time_day = data[card["CTD"]] if card["CTD"] else None
        code = data[card["CHN"]] if card["CHN"] is not None else None
        ret["check"] = SIReader._decode_time(
            data[card["CT"] : card["CT"] + 2], time_day, reftime
        )
        ret["check_code"] = SIReader._decode_station_code(code, time_day)

        if card["LT"] is not None:
            time_day = data[card["LTD"]] if card["LTD"] else None
            code = data[card["LN"]] if card["LN"] is not None else None
            ret["clear"] = SIReader._decode_time(
                data[card["LT"] : card["LT"] + 2], time_day, reftime
            )
            ret["clear_code"] = SIReader._decode_station_code(code, time_day)
        else:
            ret["clear"] = None  # SI 5 and 9 cards don't store the clear time
            ret["clear_code"] = None

        punch_count = byte2int(data[card["RC"] : card["RC"] + 1])
        if card_type == "SI5":
            # RC is the index of the next punch on SI5
            punch_count -= 1

        if punch_count > card["PM"]:
            punch_count = card["PM"]

        ret["punches"] = []
        p = 0
        i = card["P1"]
        while p < punch_count:
            if card_type == "SI5" and i % 16 == 0:
                # first byte of each block is reserved for punches 31-36
                i += 1

            ptd = data[i + card["PTD"]] if card["PTD"] is not None else None
            cn = SIReader._decode_station_code(byte2int(data[i + card["CN"]]), time_day)
            pt = data[i + card["PTH"] : i + card["PTL"] + 1]

            SIReader._append_punch(ret["punches"], cn, pt, ptd, reftime)

            i += card["PL"]
            p += 1

        return ret

    def _send_command(self, command, parameters, **kw):
        try:
            if self._serial.inWaiting() != 0:
                raise SIReaderException(
                    "Input buffer must be empty before sending command."
                    + " Currently %s bytes in the input buffer."
                    % self._serial.inWaiting()
                )
            command_string = command + int2byte(len(parameters)) + parameters
            crc = SIReader._crc(command_string)
            cmd = SIReader.STX + command_string + crc + SIReader.ETX
            if not kw.get("skipwakeup"):
                cmd = SIReader.WAKEUP + cmd
            if self._debug:
                print(
                    "==>> command '%s', parameters %s, crc %s"
                    % (
                        hexlify(command).decode("ascii"),
                        " ".join(
                            [hexlify(int2byte(c)).decode("ascii") for c in parameters]
                        ),
                        hexlify(crc).decode("ascii"),
                    )
                )
            self._serial.write(cmd)
        except (SerialException, OSError) as msg:
            raise SIReaderException("Could not send command: %s" % msg)

        if self._logfile:
            self._logfile.write("s %s %s\n" % (datetime.now(), cmd))
            self._logfile.flush()
            os.fsync(self._logfile)
        return self._read_command()

    def _read_command(self, timeout=None):
        """Receive reply from station.
        Return value is a tuple: (command_code, data).
        'command_code' is a byte
        'data' is a byte array
        'data' does not include: STX, command, length field, station code, crc and ETX
        The first byte of 'data' always seems to be 0 and does not seem to be included
        in the offsets, so 1 has to be added to the offset values when indexing the data
        returned by commands like C_GET_SYS_VAL 0x00 0x80.
        """

        try:
            if timeout != None:
                old_timeout = self._serial.timeout
                self._serial.timeout = timeout
            char = self._serial.read()
            if timeout != None:
                self._serial.timeout = old_timeout

            if char == SIReader.WAKEUP:
                # Do stations ever send WAKEUP?
                # It does not hurt to check for it...
                char = self._serial.read()

            if char == b"":
                raise SIReaderTimeout("No data available")
            elif char == SIReader.NAK:
                raise SIReaderException("Invalid command or parameter.")
            elif char != SIReader.STX:
                self._serial.flushInput()
                raise SIReaderException("Invalid start byte %s" % hex(byte2int(char)))

            # Read command, length, data, crc, ETX
            cmd = self._serial.read()
            length = self._serial.read()
            station = self._serial.read(2)
            self._station_code = SIReader._to_int(station)
            data = self._serial.read(byte2int(length) - 2)
            crc = self._serial.read(2)
            etx = self._serial.read()

            if self._debug:
                print(
                    "<<== command '%s', len %i, station %s, data %s, crc %s, etx %s"
                    % (
                        hexlify(cmd).decode("ascii"),
                        byte2int(length),
                        hexlify(station).decode("ascii"),
                        " ".join([hexlify(int2byte(c)).decode("ascii") for c in data]),
                        hexlify(crc).decode("ascii"),
                        hexlify(etx).decode("ascii"),
                    )
                )

            if etx != SIReader.ETX:
                raise SIReaderException("No ETX byte received.")
            if not SIReader._crc_check(cmd + length + station + data, crc):
                raise SIReaderException("CRC check failed")

            if self._logfile:
                self._logfile.write(
                    "r %s %s\n"
                    % (datetime.now(), char + cmd + length + station + data + crc + etx)
                )
                self._logfile.flush()
                os.fsync(self._logfile)

        except (SerialException, OSError) as msg:
            raise SIReaderException("Error reading command: %s" % msg)

        return (cmd, data)

    def _extract_sysval(bytearr, offset, length):
        """
        Extract a piece of the return data from the command C_GET_SYS_VAL '\x00\x80'.
        @param bytearr: The byte array with data from _read_command()
        @param offset:  The offset into the data (one of the SIReader.O_... constants)
        @param length:  The number of bytes to return
        @return: byte array with the extracted data
        """
        # Has to add 1 to the offset since the first byte of the data is for some reason
        # not included in the offset constants (this byte always seems to be 0)
        start = byte2int(offset) + 1
        return bytearr[start : start + length]
