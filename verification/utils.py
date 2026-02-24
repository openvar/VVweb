# verification/utils.py

import re


def is_valid_orcid(orcid: str) -> bool:
    """
    Validate an ORCID iD using ISO/IEC 7064 Mod 11-2 checksum logic.
    ORCID format: 0000-0002-1825-0097 (can end with digit or 'X')

    Returns:
        True if ORCID is valid, False otherwise.
    """

    if not orcid:
        return False

    orcid = orcid.strip().upper()

    # Must match standard ORCID pattern
    if not re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[0-9X]", orcid):
        return False

    # Remove hyphens for checksum
    digits = orcid.replace("-", "")

    total = 0
    for char in digits[:-1]:
        total = (total + int(char)) * 2

    remainder = total % 11
    result = (12 - remainder) % 11
    check_digit = "X" if result == 10 else str(result)

    return digits[-1] == check_digit

# <LICENSE>
# Copyright (C) 2016-2026 VariantValidator Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# </LICENSE>
