#!/usr/bin/env python3
"""扫描 data/ 目录，生成 OPDS 1.2 目录（封面+简介+作者）"""
import os, xml.etree.ElementTree as ET, hashlib, zipfile, re
from datetime import datetime

DATA = "data"
COVERS = "covers"
OUTPUT = "opds.xml"
ICON_URL = "https://cdn.nodeimage.com/i/Sxmax3OdSILx9MUEYWnJr3OXVctgnf6C.webp"
BASE_URL = "https://book.hellohk.me"

ATOM = "http://www.w3.org/2005/Atom"
OPDS_NS = "http://opds-spec.org/2010/catalog"
DC = "http://purl.org/dc/terms/"
DCE = "http://purl.org/dc/elements/1.1/"
OPF = "http://www.idpf.org/2007/opf"
XHTML = "http://www.w3.org/1999/xhtml"

def get_text(el):
    """递归获取元素纯文本"""
    if el is None: return ""
    parts = []
    if el.text: parts.append(el.text)
    for child in el:
        parts.append(get_text(child))
        if child.tail: parts.append(child.tail)
    return "".join(parts).strip()

def extract_content_desc(epub_path, max_chars=300):
    """从 epub 正文提取前几段作为简介"""
    try:
        with zipfile.ZipFile(epub_path) as z:
            container = z.read("META-INF/container.xml")
            root = ET.fromstring(container)
            opf_path = root.find(f".//{{{'urn:oasis:names:tc:opendocument:xmlns:container'}}}rootfile").attrib["full-path"]
            opf_dir = os.path.dirname(opf_path)

            opf = z.read(opf_path)
            opf_root = ET.fromstring(opf)
            # 找 spine 顺序
            spine = []
            for itemref in opf_root.findall(f"{{{OPF}}}spine/{{{OPF}}}itemref"):
                spine.append(itemref.attrib.get("idref"))

            # 找 manifest 中对应的 html
            manifest = {}
            for item in opf_root.findall(f"{{{OPF}}}manifest/{{{OPF}}}item"):
                manifest[item.attrib.get("id", "")] = item.attrib.get("href", "")

            # 读前几个 spine 文件，取纯文本
            for idref in spine[:3]:
                href = manifest.get(idref)
                if not href: continue
                path = os.path.normpath(os.path.join(opf_dir, href))
                try:
                    html = z.read(path).decode("utf-8", errors="ignore")
                    # 去掉 HTML 标签
                    text = re.sub(r'<[^>]+>', ' ', html)
                    text = re.sub(r'\s+', ' ', text).strip()
                    if len(text) > 50:
                        return text[:max_chars] + ("..." if len(text) > max_chars else "")
                except:
                    pass
    except:
        pass
    return None

def parse_epub_meta(epub_path):
    """从 epub 提取元数据 + 封面"""
    result = {"title": None, "author": None, "desc": None, "cover": None}
    try:
        with zipfile.ZipFile(epub_path) as z:
            container = z.read("META-INF/container.xml")
            root = ET.fromstring(container)
            opf_path = root.find(f".//{{{'urn:oasis:names:tc:opendocument:xmlns:container'}}}rootfile").attrib["full-path"]
            opf_dir = os.path.dirname(opf_path)

            opf = z.read(opf_path)
            opf_root = ET.fromstring(opf)

            meta = opf_root.find(f"{{{OPF}}}metadata")
            if meta is not None:
                t = meta.find(f"{{{DCE}}}title")
                if t is not None and t.text:
                    result["title"] = t.text.strip()
                a = meta.find(f"{{{DCE}}}creator")
                if a is not None and a.text:
                    result["author"] = a.text.strip()
                d = meta.find(f"{{{DCE}}}description")
                if d is not None and d.text and len(d.text.strip()) > 10:
                    result["desc"] = d.text.strip()[:500]

            # 封面
            cover_id = None
            for m in opf_root.findall(f"{{{OPF}}}metadata/{{{OPF}}}meta"):
                if m.attrib.get("name") == "cover":
                    cover_id = m.attrib.get("content")
                    break

            for item in opf_root.findall(f"{{{OPF}}}manifest/{{{OPF}}}item"):
                href = item.attrib.get("href", "")
                mtype = item.attrib.get("media-type", "")
                iid = item.attrib.get("id", "")
                if mtype.startswith("image/") and (iid == cover_id or "cover" in href.lower()):
                    ip = os.path.normpath(os.path.join(opf_dir, href))
                    result["cover"] = (z.read(ip), os.path.splitext(href)[1] or ".jpg")
                    break
            if result["cover"] is None:
                for item in opf_root.findall(f"{{{OPF}}}manifest/{{{OPF}}}item"):
                    if item.attrib.get("media-type", "").startswith("image/"):
                        href = item.attrib.get("href", "")
                        ip = os.path.normpath(os.path.join(opf_dir, href))
                        result["cover"] = (z.read(ip), os.path.splitext(href)[1] or ".jpg")
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
        if ext not in exts: continue
        path = os.path.join(DATA, fname)
        bid = hashlib.md5(fname.encode()).hexdigest()[:8]
        cover_file, title, author, desc = None, os.path.splitext(fname)[0], None, None

        if ext == '.epub':
            meta = parse_epub_meta(path)
            # 优先用清理后的文件名作为标题，epub内部元数据仅作作者/简介来源
            if meta["author"]: author = meta["author"]
            if meta["desc"]:
                desc = meta["desc"]
            else:
                # 回退：正文提取
                desc = extract_content_desc(path)
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
    feed = ET.Element("feed", {"xmlns": ATOM, "xmlns:opds": OPDS_NS, "xmlns:dcterms": DC})
    ET.SubElement(feed, "id").text = f"{BASE_URL}/opds.xml"
    ET.SubElement(feed, "title").text = "iimono图书馆"
    ET.SubElement(feed, "updated").text = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    a = ET.SubElement(feed, "author")
    ET.SubElement(a, "name").text = "iimono图书馆"
    ET.SubElement(feed, "link", {
        "rel": "http://opds-spec.org/icon",
        "href": ICON_URL, "type": "image/webp"})
    ET.SubElement(feed, "link", {
        "rel": "icon",
        "href": ICON_URL, "type": "image/webp"})

    for b in books:
        e = ET.SubElement(feed, "entry")
        ET.SubElement(e, "id").text = f"urn:sha1:{b['hash']}"
        ET.SubElement(e, "title").text = b['title']
        ET.SubElement(e, "updated").text = datetime.utcfromtimestamp(b['mtime']).strftime("%Y-%m-%dT%H:%M:%SZ")
        if b['author']:
            au = ET.SubElement(e, "author")
            ET.SubElement(au, "name").text = b['author']
        if b['desc']:
            ET.SubElement(e, "summary").text = b['desc']
        if b['cover']:
            ET.SubElement(e, "link", {"rel": "http://opds-spec.org/image", "href": f"{BASE_URL}/{COVERS}/{b['cover']}", "type": "image/jpeg"})
            ET.SubElement(e, "link", {"rel": "http://opds-spec.org/image/thumbnail", "href": f"{BASE_URL}/{COVERS}/{b['cover']}", "type": "image/jpeg"})
        mime_map = {'.pdf': 'application/pdf', '.epub': 'application/epub+zip', '.txt': 'text/plain'}
        mime = mime_map.get(b['ext'], 'application/octet-stream')
        ET.SubElement(e, "link", {"rel": "http://opds-spec.org/acquisition", "href": f"{BASE_URL}/data/{b['file']}", "type": mime})
        ET.SubElement(e, "dcterms:extent").text = str(b['size'])

    ET.indent(feed, space="  ")
    ET.ElementTree(feed).write(OUTPUT, encoding="utf-8", xml_declaration=True)
    c = sum(1 for b in books if b['desc'])
    print(f"生成 {OUTPUT} — {len(books)} 本 | 封面:{sum(1 for b in books if b['cover'])} 作者:{sum(1 for b in books if b['author'])} 简介:{c}")

if __name__ == "__main__":
    build_opds()
