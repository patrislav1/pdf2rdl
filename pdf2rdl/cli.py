import argparse
from pdf2rdl import __version__
from pdf2rdl.PdfScraper import PdfScraper
import logging


def parse_page_ranges(pages_desc: str) -> list[int]:
    result = []
    for p in pages_desc.split(','):
        r = [int(v) for v in p.split('-')]
        if len(r) == 1:
            result.append(r[0])
        elif len(r) == 2:
            result += list(range(r[0], r[1]+1))
        else:
            raise ValueError(f'invalid page range: {r}')
    return result


def main():
    parser = argparse.ArgumentParser(
        description='PDF scraper extracting register descriptions from data sheets'
    )
    parser.add_argument('infile',
                        type=str,
                        help='Input PDF file'
                        )
    parser.add_argument('-p', '--pages',
                        type=str,
                        help='Pages e.g. 1-5,8,11-12'
                        )
    parser.add_argument('--version',
                        action='version',
                        version='%(prog)s ' + __version__
                        )
    parser.add_argument('-v', '--verbosity',
                        type=int,
                        help='set verbosity (0=quiet, 1=info, 2=debug)'
                        )
    args = parser.parse_args()

    verbosity = args.verbosity if args.verbosity is not None else 0
    logging.basicConfig(
        format='%(levelname)7s: %(message)s',
        level=[logging.WARNING, logging.INFO, logging.DEBUG][verbosity]
    )

    pages = parse_page_ranges(args.pages) if args.pages else None

    scraper = PdfScraper(args.infile, pages)
    scraper.scrape()
