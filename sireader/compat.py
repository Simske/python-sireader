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


from six import PY3, byte2int, int2byte, iterbytes

__all__ = [
    "PY3",
    "byte2int",
    "int2byte",
    "iterbytes",
]

if PY3:
    # Make byte2int on Python 3.x compatible with
    # the fact that indexing into a byte variable
    # already returns an integer. With this byte2int(b[0])
    # works on 2.x and 3.x
    def byte2int(x):
        try:
            return x[0]
        except TypeError:
            return x
