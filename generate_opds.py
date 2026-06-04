#!/usr/bin/env python3
"""扫描 data/ 目录，生成 OPDS 1.2 目录（含封面）"""
import os, xml.etree.ElementTree as ET, hashlib, zipfile, io
from datetime import datetime

DATA = "data"
COVERS = "covers"
OUTPUT = "opds.xml"
BASE_URL = "https://book.hellohk.me"

ATOM = "http://www.w3.org/2005/Atom"
OPDS = "http://opds-spec.org/2010/catalog"
DC = "http://purl.org/dc/terms/"

def get_epub_cover(epub_path):
    """从 epub 提取封面图片，保存到 covers/，返回文件名"""
    try:
        with zipfile.ZipFile(epub_path) as z:
            # 1. 读 container.xml
            container = z.read("META-INF/container.xml")
            root = ET.fromstring(container)
            ns = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
            opf_path = root.find(".//c:rootfile", ns).attrib["full-path"]

            # 2. 读 OPF
            opf_dir = os.path.dirname(opf_path)
            opf = z.read(opf_path)
            opf_root = ET.fromstring(opf)
            opf_ns = {"opf": "http://www.idpf.org/2007/opf"}

            # 先找 cover ID
            cover_id = None
            for meta in opf_root.findall("opf:metadata/opf:meta", opf_ns):
                if meta.attrib.get("name") == "cover":
                    cover_id = meta.attrib.get("content")
                    break

            # 找 cover 图片
            for item in opf_root.findall("opf:manifest/opf:item", opf_ns):
                href = item.attrib.get("href", "")
                mtype = item.attrib.get("media-type", "")
                idx = item.attrib.get("id", "")
                if mtype.startswith("image/") and (idx == cover_id or "cover" in href.lower()):
                    img_path = os.path.normpath(os.path.join(opf_dir, href))
                    img_data = z.read(img_path)
                    ext = os.path.splitext(href)[1] or ".jpg"
                    return img_data, ext

            # 退而求其次：第一个图片
            for item in opf_root.findall("opf:manifest/opf:item", opf_ns):
                mtype = item.attrib.get("media-type", "")
                if mtype.startswith("image/"):
                    href = item.attrib.get("href", "")
                    img_path = os.path.normpath(os.path.join(opf_dir, href))
                    img_data = z.read(img_path)
                    ext = os.path.splitext(href)[1] or ".jpg"
                    return img_data, ext
    except:
        pass
    return None, None


def scan_books():
    os.makedirs(COVERS, exist_ok=True)
    books = []
    exts = {'.epub', '.pdf', '.mobi', '.azw3', '.cbz', '.cbr', '.txt'}
    for fname in sorted(os.listdir(DATA)):
        ext = os.path.splitext(fname)[1].lower()
        if ext not in exts:
            continue
        path = os.path.join(DATA, fname)
        bid = hashlib.md5(fname.encode()).hexdigest()[:8]
        cover_file = None

        # 提取封面
        if ext == '.epub':
            img_data, img_ext = get_epub_cover(path)
            if img_data:
                cover_file = f"{bid}{img_ext}"
                with open(os.path.join(COVERS, cover_file), "wb") as cf:
                    cf.write(img_data)

        books.append({
            'file': fname,
            'size': os.path.getsize(path),
            'mtime': os.path.getmtime(path),
            'hash': bid,
            'ext': ext,
            'cover': cover_file,
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

        # 封面
        if b['cover']:
            ET.SubElement(entry, "link", {
                "rel": "http://opds-spec.org/image",
                "href": f"{BASE_URL}/{COVERS}/{b['cover']}",
                "type": "image/jpeg",
            })
            ET.SubElement(entry, "link", {
                "rel": "http://opds-spec.org/image/thumbnail",
                "href": f"{BASE_URL}/{COVERS}/{b['cover']}",
                "type": "image/jpeg",
            })

        # 下载链接
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
