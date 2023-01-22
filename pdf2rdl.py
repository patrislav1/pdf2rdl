#!/usr/bin/env python3

import pdfplumber
import re


def dump_row(row):
    CELL_W = 20
    print(','.join([
        c[:CELL_W].ljust(CELL_W)
        if c is not None
        else 'N/A'.ljust(CELL_W)
        for c in row
    ]))


def rm_lf(row, cells):
    tmp = [c or '' for c in row]
    return [
        h.replace('\n', '') if en else h
        for h, en in zip(tmp, cells)
    ]


class PdfTable():
    def __init__(self, title, data):
        self.title = title
        self.hdr = [h.replace('\n', '') for h in data[0]]
        self.data = data[1:]

    def append(self, title, data):
        if not title.startswith(self.title):
            return False
        self.data += data[1:]
        return True


class RegisterDefinition():

    @staticmethod
    def is_valid(tbl: PdfTable):
        if len(tbl.hdr) != 5:
            return False
        if tbl.hdr != ['Bits', 'Name', 'Reset Value', 'Access Type', 'Description']:
            return False
        return True

    @staticmethod
    def title_addr(tbl: PdfTable):
        RE_HDR_ADDR_MATCH = re.compile(r'.+\((0x[0-9a-fA-F]+)\)$')
        addr_match = re.match(RE_HDR_ADDR_MATCH, tbl.title)
        if not addr_match:
            return None
        return int(addr_match.group(1), 0)

    def title_addr_range(tbl: PdfTable):
        RE_HDR_ADDR_RNG_MATCH = re.compile(
            r'.+\((0x[0-9a-fA-F]+)\sto\s(0x[0-9a-fA-F]+)\)$')
        addr_match = re.match(RE_HDR_ADDR_RNG_MATCH, tbl.title)
        if not addr_match:
            return None
        return int(addr_match.group(1), 0), int(addr_match.group(2), 0)

    def __init__(self, tbl: PdfTable):
        self.data = tbl.data

    def dump(self):
        for row in self.data:
            dump_row(rm_lf(row, (1, 1, 1, 1, 1)))


class RegisterMap():
    @staticmethod
    def is_valid(tbl: PdfTable):
        if not tbl.title.endswith('Register Map'):
            return False
        return True

    def __init__(self):
        self.raw_data = []
        self.title = []
        self.registers = {}

    def append_regmap(self, tbl: PdfTable):
        self.hdr = tbl.hdr
        self.title.append(tbl.title)
        self.raw_data += tbl.data

    def append_regdef(self, regaddr: int, regdef: RegisterDefinition):
        self.registers[regaddr] = regdef

    def sanitize(self):
        self.data = [
            rm_lf(row, (0, 1, 0))
            for row in self.raw_data
        ]

    RE_ADDR_MATCH = re.compile(r'(0x[0-9a-fA-F]+)$')
    RE_ADDR_RNG_MATCH = re.compile(r'(0x[0-9a-fA-F]+)\sto\s(0x[0-9a-fA-F]+)$')

    def dump(self):
        print('Title(s):')
        for t in self.title:
            print(t)
        print('Entries:')
        dump_row(self.hdr)
        print('-'*40)
        for row in self.data:
            dump_row(row)
            offs = row[0]
            addr_match = re.match(self.RE_ADDR_MATCH, offs)
            if addr_match:
                offs = (addr_match.group(1), addr_match.group(1))
            else:
                addr_match = re.match(self.RE_ADDR_RNG_MATCH, offs)
                if addr_match:
                    offs = addr_match.group(1), addr_match.group(2)
                else:
                    raise RuntimeError(
                        f'couldn\'t determine address from f{offs}')

            offs = [int(o, 0) for o in offs]
            for offs in range(offs[0], offs[0]+1, 4):
                if offs not in self.registers:
                    print(f'offset 0x{offs:02x} not in register map')
                    continue
                print('-'*40)
                self.registers[offs].dump()
                print('-'*40)


pdf = pdfplumber.open("/home/patrick/Downloads/pg125-axi-traffic-gen.pdf")
pg = pdf.pages[37:50]

curr_table = None
tables: list[PdfTable] = []

for p in pg:
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
        left, top, right, bottom = tb.bbox
        title_crop = cr.within_bbox((left, top-22, right, top))
        tb_title = title_crop.extract_text()

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
        print(f'Table not associated with register description: {tab.title}')
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
