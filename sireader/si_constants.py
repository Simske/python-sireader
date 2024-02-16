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


class SIConstants:
    """Constants with byte values needed to interact with SI stations.
    This class has a lot of constants defined that are not (yet) used.
    This is mainly for documentation purpose as most of this is not
    documented by SportIdent.
    """

    CRC_POLYNOM = 0x8005
    CRC_BITF = 0x8000

    # Protocol characters
    STX = b"\x02"  # Start of transmission
    ETX = b"\x03"  # End of transmission
    ACK = b"\x06"  # when sent to BSx3..6 with a card inserted, causes beep until SI-card taken out
    NAK = b"\x15"  # Negative ACK
    DLE = b"\x10"  # Delimiter (only used in legacy autosend data?)
    WAKEUP = b"\xFF"  # Send this byte first to wake a station up

    # Basic (legacy) protocol commands, currently unused
    BC_SET_CARDNO = b"\x30"
    BC_GET_SI5 = b"\x31"  # read out SI-card 5 data
    BC_TRANS_REC = (
        b"\x33"  # autosend timestamp (online control) in very old stations (BSF3)
    )
    BC_SI5_WRITE = (
        b"\x43"  # write SI-card 5 data page: 02 43 (page: 0x30 to 0x37) (16 bytes) 03
    )
    BC_SI5_DET = b"\x46"  # SI-card 5 inserted (46 49) or removed (46 4F)
    BC_TRANS_REC2 = b"\x53"  # autosend timestamp (online control)
    BC_TRANS_TIME = b"\x54"  # autosend timestamp (lightbeam trigger)
    BC_GET_SI6 = b"\x61"  # read out SI-card 6 data (and in compatibility mode:
    # model SI-card 8/9/10/11/SIAC/pCard/tCard as SI-card 6)
    BC_SI6_WRITEPAGE = b"\x62"  # write SI-card 6 data page: 02 62 (block: 0x00 to 0x07)
    # (page: 0x00 to 0x07) (16 bytes) 03
    BC_SI6_READWORD = b"\x63"  # read SI-card 6 data word: 02 63 (block: 0x00 to 0x07)
    # (page: 0x00 to 0x07) (word: 0x00 to 0x03) 03
    BC_SI6_WRITEWORD = b"\x64"  # write SI-card 6 data word: 02 64 (block: 0x00 to 0x07)
    # (page: 0x00 to 0x07) (word: 0x00 to 0x03) (4 bytes) 03
    BC_SI6_DET = b"\x66"  # SI-card 6 inserted
    BC_SET_MS = b"\x70"  # \x4D="M"aster, \x53="S"lave
    BC_GET_MS = b"\x71"
    BC_SET_SYS_VAL = b"\x72"
    BC_GET_SYS_VAL = b"\x73"
    BC_GET_BACKUP = b"\x74"  # Note: response carries b'\xC4'!
    BC_ERASE_BACKUP = b"\x75"
    BC_SET_TIME = b"\x76"
    BC_GET_TIME = b"\x77"
    BC_OFF = b"\x78"
    BC_RESET = b"\x79"
    BC_GET_BACKUP2 = b"\x7A"  # (for extended start and extended finish only) Note: response carries b'\xCA'!
    BC_SET_BAUD = b"\x7E"  # \x00=4800 baud, \x01=38400 baud
    # Sportident documentation says that also command 0xC4 is among the legacy commands,
    # but it does not say what that command does.

    # Extended protocol commands
    C_GET_BACKUP = b"\x81"  # Takes four bytes as parameters:
    # Three bytes as starting address and one byte as byte count.
    # The count (probably) should not be larger than 0x80.
    C_SET_SYS_VAL = b"\x82"
    C_GET_SYS_VAL = b"\x83"
    C_SRR_WRITE = b"\xA2"  # ShortRangeRadio - SysData write
    C_SRR_READ = b"\xA3"  # ShortRangeRadio - SysData read
    C_SRR_QUERY = b"\xA6"  # ShortRangeRadio - network device query
    C_SRR_PING = (
        b"\xA7"  # ShortRangeRadio - heartbeat from linked devices, every 50 seconds
    )
    C_SRR_ADHOC = b"\xA8"  # ShortRangeRadio - ad-hoc message, e.g. from SI-ActiveCard
    C_GET_SI5 = b"\xB1"  # read out SI-card 5 data
    C_SI5_WRITE = b"\xC3"  # write SI-card 5 data page: 02 C3 11 (page: 0x00 to 0x07) (16 bytes) (CRC) 03
    C_TRANS_REC = b"\xD3"  # autosend timestamp (online control)
    C_CLEAR_CARD = b"\xE0"  # found on SI-dev-forum: 02 E0 00 E0 00 03 (http://www.sportident.com/index.php?option=com_kunena&view=topic&catid=8&id=56#59)
    C_GET_SI6 = b"\xE1"  # read out SI-card 6 data block
    C_SI5_DET = b"\xE5"  # SI-card 5 inserted
    C_SI6_DET = b"\xE6"  # SI-card 6 inserted
    C_SI_REM = b"\xE7"  # SI-card removed
    C_SI9_DET = b"\xE8"  # SI-card 8/9/10/11/p/t inserted
    C_SI9_WRITE = b"\xEA"  # write data page (double-word)
    C_GET_SI9 = b"\xEF"  # read out SI-card 8/9/10/11/p/t data block
    C_SET_MS = b"\xF0"  # \x4D="M"aster, \x53="S"lave
    C_GET_MS = b"\xF1"
    C_ERASE_BACKUP = b"\xF5"
    C_SET_TIME = b"\xF6"
    C_GET_TIME = b"\xF7"
    C_OFF = b"\xF8"
    C_BEEP = b"\xF9"  # 02 F9 01 (number of beeps) (CRC16) 03
    C_SET_BAUD = b"\xFE"  # \x00=4800 baud, \x01=38400 baud

    # This is what Sportident Config+ sends to turn off the remote station.
    # It does not at all look like other commands.
    C_REMOTE_OFF = b"\xFF\x40\x0F\x80\xB2\xB6\x50\xC0"

    # Protocol Parameters
    P_MS_DIRECT = b"\x4D"  # "M"aster (direct)
    P_MS_INDIRECT = b"\x53"  # "S"lave (remote)
    P_SI6_CB = b"\x08"  # CardBlocks (see also O_SI6_CB)

    # Offsets in system data (accessed by C_SET_SYS_VAL and C_GET_SYS_VAL)
    # Thanks to Simon Harston <simon@harston.de> for most of this information
    # currently only O_MODE, O_STATION_CODE and O_PROTO are used
    O_OLD_SERIAL = b"\x00"  # 2 bytes - only up to BSx6, numbers < 65.536
    O_OLD_CPU_ID = b"\x02"  # 2 bytes - only up to BSx6, numbers < 65.536
    O_SERIAL_NO = b"\x00"  # 4 bytes - only after BSx7, numbers > 70.000
    #   (if byte 0x00 > 0, better use OLD offsets)
    O_SRR_CFG = b"\x04"  # 1 byte - SRR-dongle configuration, bit mask value:
    #   xxxxxx1xb Auto send SIAC data
    #   xxxxx1xxb Sync time via radio
    O_FIRMWARE = b"\x05"  # 3 bytes, ASCII code (e.g. "656")
    O_BUILD_DATE = b"\x08"  # 3 bytes - YYMMDD
    O_MODEL_ID = b"\x0B"  # 2 bytes:
    #   6F21: SIMSRR1-AP (ShortRangeRadio AccessPoint = SRR-dongle)
    #   8003: BSF3 (serial numbers > 1.000)
    #   8004: BSF4 (serial numbers > 10.000)
    #   8084: BSM4-RS232
    #   8086: BSM6-RS232 / BSM6-USB
    #   8115: BSF5 (serial numbers > 50.000)
    #   8117 / 8118: BSF7 / BSF8 (serial no. 70.000...70.521, 72.002...72.009)
    #   8146: BSF6 (serial numbers > 30.000)
    #   8187 / 8188: BS7-SI-Master / BS8-SI-Master
    #   8197: BSF7 (serial numbers > 71.000, apart from 72.002...72.009)
    #   8198: BSF8 (serial numbers > 80.000)
    #   9197 / 9198: BSM7-RS232, BSM7-USB / BSM8-USB, BSM8-SRR
    #   9199: unknown
    #   9597: BS7-S (Sprinter)
    #   9D9A: BS11-BL (SIAC / Air+)
    #   B197 / B198: BS7-P / BS8-P (Printer)
    #   B897: BS7-GSM
    #   CD9B: BS11-BS-red / BS11-BS-blue (SIAC / Air+)

    O_MEM_SIZE = b"\x0D"  # 1 byte - in KB
    O_BAT_DATE = b"\x15"  # 3 bytes - YYMMDD
    O_BAT_CAP = b"\x19"  # 2 bytes - battery capacity in mAh (as multiples of 16/225 = 0.0711 mAh?!)
    O_BACKUP_PTR_HI = b"\x1C"  # 2 bytes - high bytes of backup memory pointer
    O_BACKUP_PTR_LO = b"\x21"  # 2 bytes - low bytes of backup pointer
    # The pointer information can be used with the C_GET_BACKUP command.
    O_SI6_CB = b"\x33"  # 1 byte - bitfield defining which SI Card 6 blocks to read:
    #   \x00=\xC1=read block0,6,7; \x08=\xFF=read all 8 blocks
    #   all 8 blocks are used when supporting 192 punches
    O_SRR_CHANNEL = (
        b"\x34"  # 1 byte - SRR-dongle frequency band: 0x00="red", 0x01="blue"
    )
    O_USED_BAT_CAP = b"\x35"  # 3 byte - Used battery capacity. Multiply by 2.778e-5 to get percent used
    # (Comment used to say 'multiply by 1.38e-3', but this seems incorrect)
    O_MEM_OVERFLOW = b"\x3D"  # 1 byte - memory overflow if != 0x00
    O_BAT_VOLT = b"\x50"  # 2 byte - battery voltage, multiply by 5/65536 V
    O_PROGRAM = (
        b"\x70"  # 1 byte - station program: xx0xxxxxb competition, xx1xxxxxb training
    )
    O_MODE = b"\x71"  # 1 byte - see SI station modes below
    O_STATION_CODE = b"\x72"  # 1 byte - lower bits of station code
    O_FEEDBACK = b"\x73"  # 1 byte - feedback on punch, MSBits of code
    # (and other unknown bits), bit mask value:
    #   xxxxxxx1b optical feedback
    #   xxxxx1xxb audible feedback
    #   11xxxxxxb MSBits of station code
    O_PROTO = b"\x74"  # 1 byte - protocol configuration, bit mask value:
    #   xxxxxxx1b extended protocol
    #   xxxxxx1xb auto send out
    #   xxxxx1xxb handshake (only valid for card readout)
    #   xxx1xxxxb access with password only
    #   1xxxxxxxb read out SI-card after punch (only for punch modes;
    #             depends on bit 2: auto send out or handshake)
    O_WAKEUP_DATE = b"\x75"  # 3 bytes - YYMMDD
    O_WAKEUP_TIME = b"\x78"  # 3 bytes - 1 byte day (see below), 2 bytes seconds after midnight/midday
    O_SLEEP_TIME = b"\x7B"  # 3 bytes - 1 byte day (see below), 2 bytes seconds after midnight/midday
    #   xxxxxxx0b - seconds relative to midnight/midday: 0 = am, 1 = pm
    #   xxxx000xb - day of week: 000 = Sunday, 110 = Saturday
    #   xx00xxxxb - week counter 0..3, relative to programming date
    O_ACTIVE_TIME = (
        b"\x7E"  # 2 bytes - station active time in minutes, max 5759 minutes (< 96h)
    )

    # SI station modes
    M_SIAC_SPECIAL = 0x01  # SI Air+ special register set (ON, OFF, Radio_ReadOut, etc.)
    M_CONTROL = 0x02
    M_START = 0x03
    M_FINISH = 0x04
    M_READOUT = 0x05
    M_CLEAR_OLD = 0x06  # without start-number (not used anymore)
    M_CLEAR = 0x07  # with start-number = standard
    M_CHECK = 0x0A
    M_PRINTOUT = 0x0B  # BS7-P Printer-station (Note: also used by SRR-Receiver-module)
    M_START_TRIG = 0x0C  # BS7-S (Sprinter) with external trigger
    M_FINISH_TRIG = 0x0D  # BS7-S (Sprinter) with external trigger
    M_BC_CONTROL = 0x12  # SI Air+ / SIAC Beacon mode
    M_BC_START = 0x13  # SI Air+ / SIAC Beacon mode
    M_BC_FINISH = 0x14  # SI Air+ / SIAC Beacon mode
    M_BC_READOUT = 0x15  # SI Air+ / SIAC Beacon mode
    SUPPORTED_MODES = (M_CONTROL, M_START, M_FINISH, M_READOUT, M_CLEAR, M_CHECK)
    SUPPORTED_READ_BACKUP_MODES = (
        M_CONTROL,
        M_START,
        M_FINISH,
        M_CLEAR_OLD,
        M_CLEAR,
        M_CHECK,
    )
    MODE2NAME = {
        M_SIAC_SPECIAL: "SIAC special",
        M_CONTROL: "Control",
        M_START: "Start",
        M_FINISH: "Finish",
        M_READOUT: "Readout",
        M_CLEAR_OLD: "Clear old",
        M_CLEAR: "Clear",
        M_CHECK: "Check",
        M_PRINTOUT: "Printout",
        M_START_TRIG: "Start trig",
        M_FINISH_TRIG: "Finish trig",
        M_BC_CONTROL: "BC control",
        M_BC_START: "BC start",
        M_BC_FINISH: "BC finish",
        M_BC_READOUT: "BC readout",
    }

    MODEL2NAME = {
        0x6F21: "SIMSRR1-AP",  # (ShortRangeRadio AccessPoint = SRR-dongle)
        0x8003: "BSF3",  # BSF3 (serial numbers > 1.000)
        0x8004: "BSF4",  # (serial numbers > 10.000)
        0x8084: "BSM4-RS232",
        0x8086: "BSM6-RS232/USB",
        0x8115: "BSF5",  # (serial numbers > 50.000)
        0x8117: "BSF7",  # (serial no. 70.000...70.521, 72.002...72.009)
        0x8118: "BSF8",  # (serial no. 70.000...70.521, 72.002...72.009)
        0x8146: "BSF6",  # (serial numbers > 30.000)
        0x8187: "BS7-SI-Master",
        0x8188: "BS8-SI-Master",
        0x8197: "BSF7",  # (serial numbers > 71.000, apart from 72.002...72.009)
        0x8198: "BSF8",  # (serial numbers > 80.000)
        0x9197: "BSM7-RS232/USB",
        0x9198: "BSM8-USB/SRR",
        0x9199: "unknown",
        0x9597: "BS7-S",  # (Sprinter)
        0x9D9A: "BS11-BL",  # (SIAC / Air+)
        0xB197: "BS7-P",  # (Printer)
        0xB198: "BS8-P",  # (Printer)
        0xB897: "BS7-GSM",
        0xCD9B: "BS11-BS",  # -red / -blue (SIAC / Air+)
    }

    # Weekday encoding (only for reference, currently unused)
    D_SUNDAY = 0b000
    D_MONDAY = 0b001
    D_TUESDAY = 0b010
    D_WEDNESDAY = 0b011
    D_THURSDAY = 0b100
    D_FRIDAY = 0b101
    D_SATURDAY = 0b110
    D_UNKNOWN = (
        0b111  # in D3-message from SIAC-beacon where no weekday-info is transmitted
    )

    # Backup memory record length
    REC_LEN = 8  # Only in extended protocol, otherwise 6!

    # General card data structure values
    TIME_RESET = b"\xEE\xEE"

    # SI Card data structures
    CARD = {
        "SI5": {
            "CN2": 6,  # card number byte 2
            "CN1": 4,  # card number byte 1
            "CN0": 5,  # card number byte 0
            "STD": None,  # start time day
            "SN": None,  # start number
            "ST": 19,  # start time
            "FTD": None,  # finish time day
            "FN": None,  # finish number
            "FT": 21,  # finish time
            "CTD": None,  # check time day
            "CHN": None,  # check number
            "CT": 25,  # check time
            "LTD": None,  # clear time day
            "LN": None,  # clear number
            "LT": None,  # clear time
            "RC": 23,  # punch counter
            "P1": 32,  # first punch
            "PL": 3,  # punch data length in bytes
            "PM": 30,  # punch maximum (punches 31-36 have no time)
            "CN": 0,  # control number offset in punch record
            "PTD": None,  # punchtime day byte offset in punch record
            "PTH": 1,  # punchtime high byte offset in punch record
            "PTL": 2,  # punchtime low byte offset in punch record
        },
        "SI6": {
            "CN2": 11,
            "CN1": 12,
            "CN0": 13,
            "STD": 24,
            "SN": 25,
            "ST": 26,
            "FTD": 20,
            "FN": 21,
            "FT": 22,
            "CTD": 28,
            "CHN": 29,
            "CT": 30,
            "LTD": 32,
            "LN": 33,
            "LT": 34,
            "RC": 18,
            "P1": 128,
            "PL": 4,
            "PM": 64,
            "PTD": 0,  # Day of week byte, SI6 and newer
            "CN": 1,
            "PTH": 2,
            "PTL": 3,
        },
        "SI8": {
            "CN2": 25,
            "CN1": 26,
            "CN0": 27,
            "STD": 12,
            "SN": 13,
            "ST": 14,
            "FTD": 16,
            "FN": 17,
            "FT": 18,
            "CTD": 8,
            "CHN": 9,
            "CT": 10,
            "LTD": None,
            "LN": None,
            "LT": None,
            "RC": 22,
            "P1": 136,
            "PL": 4,
            "PM": 50,
            "PTD": 0,
            "CN": 1,
            "PTH": 2,
            "PTL": 3,
            "BC": 2,  # number of blocks on card (only relevant for SI8 and above = those read with C_GET_SI9)
        },
        "SI9": {
            "CN2": 25,
            "CN1": 26,
            "CN0": 27,
            "STD": 12,
            "SN": 13,
            "ST": 14,
            "FTD": 16,
            "FN": 17,
            "FT": 18,
            "CTD": 8,
            "CHN": 9,
            "CT": 10,
            "LTD": None,
            "LN": None,
            "LT": None,
            "RC": 22,
            "P1": 56,
            "PL": 4,
            "PM": 50,
            "PTD": 0,
            "CN": 1,
            "PTH": 2,
            "PTL": 3,
            "BC": 2,
        },
        "pCard": {
            "CN2": 25,  # Similar to SI9/10 but not identical
            "CN1": 26,
            "CN0": 27,
            "STD": 12,
            "SN": 13,
            "ST": 14,
            "FTD": 16,
            "FN": 17,
            "FT": 18,
            "CTD": 8,
            "CHN": 9,
            "CT": 10,
            "LTD": None,
            "LN": None,
            "LT": None,
            "RC": 22,
            "P1": 176,  # Location of Punch 1 I believe
            "PL": 4,
            "PM": 20,
            "PTD": 0,
            "CN": 1,
            "PTH": 2,
            "PTL": 3,
            "BC": 2,
        },
        "SI10": {
            "CN2": 25,  # Same data structure for SI11
            "CN1": 26,
            "CN0": 27,
            "STD": 12,
            "SN": 13,
            "ST": 14,
            "FTD": 16,
            "FN": 17,
            "FT": 18,
            "CTD": 8,
            "CHN": 9,
            "CT": 10,
            "LTD": None,
            "LN": None,
            "LT": None,
            "RC": 22,
            "P1": 128,  # would be 512 if all blocks were read, but blocks 1-3 are skipped on readout
            "PL": 4,
            "PM": 64,
            "PTD": 0,
            "CN": 1,
            "PTH": 2,
            "PTL": 3,
            "BC": 8,
        },
    }

    # punch trigger in control mode data structure
    T_OFFSET = 8
    T_CN = 0
    T_TIME = 5

    # backup memory in control mode
    BC_CN = 3
    BC_TIME = 8

    # offsets in backup memory readout of controls, extended protocol
    BUX_FIRST = 2  # First punch begins at this offset in the data (add 1 like for the O_ constants)
    BUX_SIZE = 8  # Each record is 8 bytes long
    # offsets within each punch record
    BUX_CN = 0  # 3 bytes, MSB to LSB
    BUX_YM = 3  # 1 byte, bits 7..2: year (0 means 2000), bits 1..0: upper bits of month
    BUX_MDAP = 4  # 1 byte, bits 7..6: lower bits of month, bits 5..1: day of month, bit 0: AM/PM
    BUX_SECS = 5  # 2 bytes, seconds since midnight or midday
    BUX_MS = 7  # 1 byte, divide by 256 to get fractions of seconds

    # offsets in backup memory readout of controls, legacy protocol
    BUL_FIRST = 2  # First punch begins at this offset in the data (add 1 like for the O_ constants)
    BUL_SIZE = 6  # Each record is 6 bytes long
    # offsets within each punch record
    BUL_CN = 0  # 2 bytes, lower part of card number
    BUL_SECS = 2  # 2 bytes, seconds since midnight/midday
    BUL_PTD = 4  # 1 byte
    # bit 0 - am/pm
    # bit 3...1 - day of week, 000 = Sunday, 110 = Saturday
    # bit 5...4 - week counter 0...3, relative, not used, seems to always be 0
    # bit 7...6 - control station code number high
    # (...511)
    BUL_CNS = 5  # 1 byte, card number series(?)
    # Multiply by 100 000 if <= 4 (SI5), otherwise multiply by 65536 (?)
