#!/usr/bin/env python3

import pdfplumber


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

    def __init__(self, tbl: PdfTable):
        self.tab = tbl


class RegisterMap():
    @staticmethod
    def is_valid(tbl: PdfTable):
        if not tbl.title.endswith('Register Map'):
            return False
        return True

    def __init__(self):
        self.data = []
        self.title = []
        self.registers = []

    def append_regmap(self, tbl: PdfTable):
        self.title.append(tbl.title)
        self.data.append(tbl.data)

    def append_regdef(self, tbl: PdfTable):
        self.registers.append(tbl)


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
        regmap.append_regdef(tab)
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
