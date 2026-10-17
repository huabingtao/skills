"""Move unambiguous diamond units from numeric table cells into column headers."""

import re


NUMBER = r"\d+(?:\.\d+)?(?:[wW万亿])?"
VALUE = re.compile(rf"^\s*{NUMBER}\s*(?:钻石|钻)?\s*$")
UNIT = re.compile(r"钻石|钻")
HEADER_UNIT = re.compile(r"钻石|[（(]\s*钻\s*[）)]|^钻$")


def normalize_diamond_table_units(soup):
    """Skip mixed-currency/prose/merged columns instead of changing their meaning."""
    for table in soup.find_all("table"):
        rows = [r.find_all(["th", "td"], recursive=False) for r in table.find_all("tr")]
        if len(rows) < 2 or not rows[0] or not all(c.name == "th" for c in rows[0]):
            continue
        if any(len(row) != len(rows[0]) for row in rows) or table.find(attrs={"colspan": True}) or table.find(attrs={"rowspan": True}):
            continue
        for col, header in enumerate(rows[0]):
            cells = [row[col] for row in rows[1:]]
            has_unit = bool(HEADER_UNIT.search(header.get_text(strip=True)))
            numeric = True
            for cell in cells:
                if cell.find(["br", "table", "ul", "ol", "code"]):
                    numeric = False
                    break
                text = cell.get_text(strip=True)
                images = cell.find_all("img")
                if any(img.get("alt") != "钻石" for img in images):
                    numeric = False
                    break
                if text not in ("", "—", "-") and not VALUE.fullmatch(text):
                    numeric = False
                    break
                has_unit = has_unit or bool(UNIT.search(text)) or bool(images)
            if not numeric or not has_unit:
                continue
            if not HEADER_UNIT.search(header.get_text(strip=True)):
                header.append("（钻石）")
            for cell in cells:
                for node in list(cell.find_all(string=True)):
                    node.replace_with(UNIT.sub("", str(node)))
                for img in list(cell.find_all("img")):
                    img.decompose()
