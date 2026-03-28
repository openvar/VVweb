# verification/validators.py

import re
from urllib.parse import urlparse


# ---------------------------
# ORCID VALIDATION
# ---------------------------
def is_valid_orcid(orcid: str) -> bool:
    """
    Validate an ORCID iD using ISO/IEC 7064 Mod 11-2.
    Example valid: 0000-0002-1825-0097
    """

    if not orcid:
        return False

    orcid = orcid.strip().upper()

    if not re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[0-9X]", orcid):
        return False

    digits = orcid.replace("-", "")
    total = 0

    for char in digits[:-1]:
        total = (total + int(char)) * 2

    remainder = total % 11
    result = (12 - remainder) % 11
    check_digit = "X" if result == 10 else str(result)

    return digits[-1] == check_digit


# ---------------------------
# GENERIC URL SANITY CHECK
# ---------------------------
def is_valid_url(url: str) -> bool:
    """Basic sanity check for URLs."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme and parsed.netloc)
    except Exception:
        return False


# ---------------------------
# GOOGLE SCHOLAR DETECTOR
# ---------------------------
def is_probable_google_scholar(url: str) -> bool:
    """
    Identify Google Scholar profile URLs.
    Example:
      https://scholar.google.com/citations?user=XXXXXX
    """
    if not is_valid_url(url):
        return False
    parsed = urlparse(url)
    return ("scholar.google" in parsed.netloc.lower()
            and "/citations" in parsed.path.lower())


# ---------------------------
# LINKEDIN DETECTOR
# ---------------------------
def is_linkedin_profile(url: str) -> bool:
    if not is_valid_url(url):
        return False
    parsed = urlparse(url)
    return "linkedin.com" in parsed.netloc.lower()


# ---------------------------
# COMPANY PAGE DETECTOR
# ---------------------------
def looks_like_company_site(url: str) -> bool:
    """
    Very naive heuristic, but helps flag commercial users.
    """
    if not is_valid_url(url):
        return False
    company_keywords = ["team", "company", "about", "consult", "bio"]
    parsed = urlparse(url)
    return any(k in parsed.path.lower() for k in company_keywords)


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
