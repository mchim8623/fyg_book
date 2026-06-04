#!/usr/bin/env python3
"""扫描 data/ 目录，生成 OPDS 1.2 目录（封面+简介）"""
import os, xml.etree.ElementTree as ET, hashlib, zipfile
from datetime import datetime

DATA = "data"
COVERS = "covers"
OUTPUT = "opds.xml"
BASE_URL = "https://book.hellohk.me"

ATOM = "http://www.w3.org/2005/Atom"
OPDS = "http://opds-spec.org/2010/catalog"
DC = "http://purl.org/dc/terms/"

def parse_epub_meta(epub_path):
    """从 epub 提取封面、标题、简介、作者"""
    result = {"title": None, "author": None, "desc": None, "cover": None}
    try:
        with zipfile.ZipFile(epub_path) as z:
            container = z.read("META-INF/container.xml")
            root = ET.fromstring(container)
            ns_c = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
            opf_path = root.find(".//c:rootfile", ns_c).attrib["full-path"]
            opf_dir = os.path.dirname(opf_path)

            opf = z.read(opf_path)
            opf_root = ET.fromstring(opf)
            # 注册命名空间
            ns_map = {
                "opf": "http://www.idpf.org/2007/opf",
                "dc": "http://purl.org/dc/elements/1.1/",
            }

            meta = opf_root.find("opf:metadata", ns_map)
            if meta is not None:
                # 标题
                t = meta.find("dc:title", ns_map)
                if t is not None and t.text:
                    result["title"] = t.text.strip()
                # 作者
                a = meta.find("dc:creator", ns_map)
                if a is not None and a.text:
                    result["author"] = a.text.strip()
                # 简介
                d = meta.find("dc:description", ns_map)
                if d is not None and d.text:
                    desc = d.text.strip()
                    # 截断过长的简介
                    if len(desc) > 500:
                        desc = desc[:500] + "..."
                    result["desc"] = desc

            # 封面
            cover_id = None
            for m in opf_root.findall("opf:metadata/opf:meta", ns_map):
                if m.attrib.get("name") == "cover":
                    cover_id = m.attrib.get("content")
                    break

            for item in opf_root.findall("opf:manifest/opf:item", ns_map):
                href = item.attrib.get("href", "")
                mtype = item.attrib.get("media-type", "")
                iid = item.attrib.get("id", "")
                if mtype.startswith("image/") and (iid == cover_id or "cover" in href.lower()):
                    img_path = os.path.normpath(os.path.join(opf_dir, href))
                    img_data = z.read(img_path)
                    ext = os.path.splitext(href)[1] or ".jpg"
                    result["cover"] = (img_data, ext)
                    break

            # 退而求其次
            if result["cover"] is None:
                for item in opf_root.findall("opf:manifest/opf:item", ns_map):
                    if item.attrib.get("media-type", "").startswith("image/"):
                        href = item.attrib.get("href", "")
                        img_path = os.path.normpath(os.path.join(opf_dir, href))
                        result["cover"] = (z.read(img_path), os.path.splitext(href)[1] or ".jpg")
                        break
    except:
        pass
    return result


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
        title = os.path.splitext(fname)[0]
        author = None
        desc = None

        if ext == '.epub':
            meta = parse_epub_meta(path)
            if meta["title"]:
                title = meta["title"]
            if meta["author"]:
                author = meta["author"]
            if meta["desc"]:
                desc = meta["desc"]
            if meta["cover"]:
                img_data, img_ext = meta["cover"]
                cover_file = f"{bid}{img_ext}"
                with open(os.path.join(COVERS, cover_file), "wb") as cf:
                    cf.write(img_data)

        books.append({
            'file': fname, 'size': os.path.getsize(path),
            'mtime': os.path.getmtime(path), 'hash': bid,
            'ext': ext, 'cover': cover_file,
            'title': title, 'author': author, 'desc': desc,
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

    # 图标
    ET.SubElement(feed, "link", {
        "rel": "http://opds-spec.org/icon",
        "href": f"{BASE_URL}/icon.png",
        "type": "image/png",
    })

    for b in books:
        entry = ET.SubElement(feed, "entry")
        ET.SubElement(entry, "id").text = f"urn:sha1:{b['hash']}"
        ET.SubElement(entry, "title").text = b['title']
        ET.SubElement(entry, "updated").text = datetime.utcfromtimestamp(b['mtime']).strftime("%Y-%m-%dT%H:%M:%SZ")

        if b['author']:
            au = ET.SubElement(entry, "author")
            ET.SubElement(au, "name").text = b['author']

        if b['desc']:
            ET.SubElement(entry, "summary").text = b['desc']

        if b['cover']:
            ET.SubElement(entry, "link", {
                "rel": "http://opds-spec.org/image",
                "href": f"{BASE_URL}/{COVERS}/{b['cover']}", "type": "image/jpeg"})
            ET.SubElement(entry, "link", {
                "rel": "http://opds-spec.org/image/thumbnail",
                "href": f"{BASE_URL}/{COVERS}/{b['cover']}", "type": "image/jpeg"})

        mime = "application/pdf" if b['ext'] == '.pdf' else "application/epub+zip"
        ET.SubElement(entry, "link", {
            "rel": "http://opds-spec.org/acquisition",
            "href": f"{BASE_URL}/data/{b['file']}", "type": mime})
        ET.SubElement(entry, "dcterms:extent").text = str(b['size'])

    ET.indent(feed, space="  ")
    ET.ElementTree(feed).write(OUTPUT, encoding="utf-8", xml_declaration=True)

    has_desc = sum(1 for b in books if b['desc'])
    has_author = sum(1 for b in books if b['author'])
    has_cover = sum(1 for b in books if b['cover'])
    print(f"生成 {OUTPUT} — {len(books)} 本 | 封面:{has_cover} 作者:{has_author} 简介:{has_desc}")

if __name__ == "__main__":
    build_opds()
