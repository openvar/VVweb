import json

def format_input(data_string):
    """
    Takes an input string. Tries to convert from JSON to list, otherwise converts a string into a list.
    Then goes on to check for pipe delimited data and splits if necessary.
    The output is always a JSON array.
    """

    # Optional safety: preserve real lists
    if isinstance(data_string, list):
        return json.dumps(data_string)

    data_string = str(data_string)

    try:
        data_list = json.loads(data_string)
    except json.decoder.JSONDecodeError:
        # Protect |gom and |lom tokens
        data_intermediate = data_string.replace("|gom", "&amp;gom").replace("|lom", "&amp;lom")
        pre_data_list = data_intermediate.split("|")

        data_list = []
        for entry in pre_data_list:
            data_list.append(entry.replace("&amp;", "|"))

    return json.dumps(data_list)

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
