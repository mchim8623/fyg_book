#!/usr/bin/env python3
"""扫描 data/ 目录，生成 OPDS 1.2 目录"""
import os, xml.etree.ElementTree as ET, hashlib
from datetime import datetime

DATA = "data"
OUTPUT = "opds.xml"
BASE_URL = "https://book.hellohk.me"

ATOM = "http://www.w3.org/2005/Atom"
OPDS = "http://opds-spec.org/2010/catalog"
DC = "http://purl.org/dc/terms/"

def scan_books():
    books = []
    exts = {'.epub', '.pdf', '.mobi', '.azw3', '.cbz', '.cbr', '.txt'}
    for fname in sorted(os.listdir(DATA)):
        ext = os.path.splitext(fname)[1].lower()
        if ext in exts:
            path = os.path.join(DATA, fname)
            books.append({
                'file': fname,
                'size': os.path.getsize(path),
                'mtime': os.path.getmtime(path),
                'hash': hashlib.md5(fname.encode()).hexdigest()[:8],
                'ext': ext,
            })
    return books

def build_opds():
    books = scan_books()
    feed = ET.Element("feed", {"xmlns": ATOM, "xmlns:opds": OPDS, "xmlns:dcterms": DC})
    ET.SubElement(feed, "id").text = f"{BASE_URL}/opds.xml"
    ET.SubElement(feed, "title").text = "iimono图书馆"
    ET.SubElement(feed, "updated").text = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    author = ET.SubElement(feed, "author")
    ET.SubElement(author, "name").text = "iimono图书馆"

    for b in books:
        entry = ET.SubElement(feed, "entry")
        ET.SubElement(entry, "id").text = f"urn:sha1:{b['hash']}"
        ET.SubElement(entry, "title").text = os.path.splitext(b['file'])[0]
        ET.SubElement(entry, "updated").text = datetime.utcfromtimestamp(b['mtime']).strftime("%Y-%m-%dT%H:%M:%SZ")
        mime = "application/pdf" if b['ext'] == '.pdf' else "application/epub+zip"
        ET.SubElement(entry, "link", {
            "rel": "http://opds-spec.org/acquisition",
            "href": f"{BASE_URL}/data/{b['file']}",
            "type": mime,
        })
        ET.SubElement(entry, "dcterms:extent").text = str(b['size'])

    ET.indent(feed, space="  ")
    tree = ET.ElementTree(feed)
    tree.write(OUTPUT, encoding="utf-8", xml_declaration=True)
    print(f"生成 {OUTPUT} — {len(books)} 本书")

if __name__ == "__main__":
    build_opds()
