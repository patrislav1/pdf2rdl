#!/usr/bin/env python3

import re
from typing import Optional, Tuple
import pdfplumber


def dump_row(row: list[str]) -> None:
    CELL_W = 20
    print(','.join([
        c[:CELL_W].ljust(CELL_W)
        if c is not None
        else 'N/A'.ljust(CELL_W)
        for c in row
    ]))


def rm_lf(row: list[Optional[str]], cells: Tuple[bool, ...]) -> list[str]:
    tmp = [c or '' for c in row]
    return [
        h.replace('\n', '') if en else h
        for h, en in zip(tmp, cells)
    ]


class PdfTable():
    def __init__(self, title: str, data: list[list[Optional[str]]]):
        self.title = title
        self.hdr = [h.replace('\n', '') if h else '' for h in data[0]]
        self.data = data[1:]

    def append(self, title: str, data: list[list[Optional[str]]]) -> bool:
        if not title.startswith(self.title):
            return False
        self.data += data[1:]
        return True


class RegisterDefinition():

    @staticmethod
    def is_valid(tbl: PdfTable) -> bool:
        if len(tbl.hdr) != 5:
            return False
        if tbl.hdr != ['Bits', 'Name', 'Reset Value', 'Access Type', 'Description']:
            return False
        return True

    @staticmethod
    def title_addr(tbl: PdfTable) -> Optional[int]:
        RE_HDR_ADDR_MATCH = re.compile(r'.+\((0x[0-9a-fA-F]+)\)$')
        addr_match = re.match(RE_HDR_ADDR_MATCH, tbl.title)
        if not addr_match:
            return None
        return int(addr_match.group(1), 0)

    @staticmethod
    def title_addr_range(tbl: PdfTable) -> Optional[Tuple[int, int]]:
        RE_HDR_ADDR_RNG_MATCH = re.compile(
            r'.+\((0x[0-9a-fA-F]+)\sto\s(0x[0-9a-fA-F]+)\)$')
        addr_match = re.match(RE_HDR_ADDR_RNG_MATCH, tbl.title)
        if not addr_match:
            return None
        return int(addr_match.group(1), 0), int(addr_match.group(2), 0)

    def __init__(self, tbl: PdfTable):
        self.data = tbl.data

    def dump(self) -> None:
        for row in self.data:
            dump_row(rm_lf(row, (True, ) * len(row)))


class RegisterMap():
    @staticmethod
    def is_valid(tbl: PdfTable) -> bool:
        if not tbl.title.endswith('Register Map'):
            return False
        return True

    def __init__(self) -> None:
        self.raw_data: list[list[Optional[str]]] = []
        self.title: list[str] = []
        self.registers: dict[int, RegisterDefinition] = {}

    def append_regmap(self, tbl: PdfTable) -> None:
        self.hdr = tbl.hdr
        self.title.append(tbl.title)
        self.raw_data += tbl.data

    def append_regdef(self, regaddr: int, regdef: RegisterDefinition) -> None:
        self.registers[regaddr] = regdef

    def sanitize(self) -> None:
        self.data = [
            rm_lf(row, (False, True, False))
            for row in self.raw_data
        ]

    RE_ADDR_MATCH = re.compile(r'(0x[0-9a-fA-F]+)$')
    RE_ADDR_RNG_MATCH = re.compile(r'(0x[0-9a-fA-F]+)\sto\s(0x[0-9a-fA-F]+)$')

    def dump(self) -> None:
        print('Title(s):')
        for t in self.title:
            print(t)
        print('Entries:')
        dump_row(self.hdr)
        print('-'*40)
        for row in self.data:
            dump_row(row)
            offs_str = row[0]
            addr_match = re.match(self.RE_ADDR_MATCH, offs_str)
            if addr_match:
                offs_fields = (addr_match.group(1), addr_match.group(1))
            else:
                addr_match = re.match(self.RE_ADDR_RNG_MATCH, offs_str)
                if addr_match:
                    offs_fields = addr_match.group(1), addr_match.group(2)
                else:
                    raise RuntimeError(
                        f'couldn\'t determine address from f{offs_str}')

            offs_rng = [int(o, 0) for o in offs_fields]
            for offs in range(offs_rng[0], offs_rng[0]+1, 4):
                if offs not in self.registers:
                    print(f'offset 0x{offs:02x} not in register map')
                    continue
                print('-'*40)
                self.registers[offs].dump()
                print('-'*40)


class PdfScraper():
    def __init__(self, fname: str, pages: Optional[list[int]] = None):
        self.pdf = pdfplumber.open(fname)
        if pages is None:
            self.pages = self.pdf.pages
        else:
            self.pages = [self.pdf.pages[p] for p in pages]

    def scrape(self) -> None:
        curr_table: Optional[PdfTable] = None
        tables: list[PdfTable] = []

        for p in self.pages:
            w, h, mr = p.width, p.height, 0.08
            cr = p.crop((w * mr*1.4, h * mr, w * (1-mr), h * (1-mr)))

            tbset = {
                'snap_x_tolerance': 5,
                'snap_y_tolerance': 5,
            }
            tbs = cr.find_tables(table_settings=tbset)

            for tb in tbs:
                tb_data = tb.extract()
                # Get the coordinates of the table
                left, top, right, _ = tb.bbox
                try:
                    title_crop = cr.within_bbox((left, top-22, right, top))
                    tb_title = title_crop.extract_text()
                except ValueError:
                    continue

                if curr_table is not None:
                    if curr_table.append(tb_title, tb_data):
                        continue
                    tables.append(curr_table)

                curr_table = PdfTable(tb_title.strip(), tb_data)

        if curr_table is not None:
            tables.append(curr_table)

        regmap = RegisterMap()

        for tab in tables:
            if RegisterMap.is_valid(tab):
                print(f'Adding to regmap: {tab.title}')
                regmap.append_regmap(tab)
            elif RegisterDefinition.is_valid(tab):
                print(f'Adding regdesc: {tab.title}')
                regaddr = RegisterDefinition.title_addr(tab)
                if regaddr is not None:
                    regdef = RegisterDefinition(tab)
                    regmap.append_regdef(regaddr, regdef)
                else:
                    regaddr_range = RegisterDefinition.title_addr_range(tab)
                    if regaddr_range is not None:
                        for addr in range(regaddr_range[0], regaddr_range[1] + 1, 4):
                            regmap.append_regdef(addr, regdef)
            else:
                print(
                    f'Table not associated with register description: {tab.title}')
            '''
            print(tab.title)
            for row in [tab.hdr] + tab.data:
                for col in row:
                    if col is not None:
                        s = col[:10].ljust(10)
                    else:
                        s = 'N/A'
                    print(s + ', ', end='')
                print()
            print('-'*40)
            '''

        regmap.sanitize()
        regmap.dump()
