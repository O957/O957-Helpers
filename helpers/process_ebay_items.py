"""
Processes ebay items strings copied from ebay messages. In the ebay messages,
the strings annoyingly are joined. Each string is (always?) 12 characters long.
"""

import textwrap
from pprint import pprint


def format_ebay_item_strs(ebay_items_str: str, wrap_length: int) -> str:
    if len(ebay_items_str) % wrap_length == 0:
        return textwrap.wrap(ebay_items_str, wrap_length)


print("NEW MEXICO")
pprint(
    format_ebay_item_strs(
        "375719801352375764351126375462693195376627749851376593866520376593846977376435667662376363190908376363165879376362891536376362890256376505297005376593862136376593857447376363183963376363180033376362901198376362897244376362891088376362889226376357518595376322210351376180799809376180797500376178550492376348413280",
        12,
    )
)
