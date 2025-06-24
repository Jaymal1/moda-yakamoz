import xml.etree.ElementTree as ET
import xml.dom.minidom
import os
import json
from datetime import datetime
from deep_translator import GoogleTranslator
import requests

# Constants
RAW_XML_FILE = "modayakamoz_raw.xml"
OUTPUT_FILE = "translatedsample_yakamoz.xml"
TRANSLATED_IDS_FILE = "translated_ids_yakamoz.json"
EXCHANGE_RATE_API = "https://api.exchangerate.host/latest?base=TRY&symbols=USD"

def pretty_print_xml(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_xml = f.read()
        dom = xml.dom.minidom.parseString(raw_xml)
        pretty_xml_as_str = dom.toprettyxml(indent="  ")
        print("Pretty printed XML preview (first 500 chars):")
        print(pretty_xml_as_str[:500])
    except Exception as e:
        print(f"[ERROR] Pretty print failed: {e}")

def get_exchange_rate():
    try:
        res = requests.get(EXCHANGE_RATE_API, timeout=10)
        res.raise_for_status()
        data = res.json()
        print("[INFO] Exchange rate response:", data)
        return data['rates']['USD']
    except Exception as e:
        print(f"[WARNING] Using fallback exchange rate due to error: {e}")
        return 0.031  # fallback rate

def translate_text(text):
    if not text or text.strip() == '':
        return text
    try:
        return GoogleTranslator(source='tr', target='en').translate(text)
    except Exception as e:
        print(f"[WARNING] Translation failed: {e}")
        return text

def load_translated_ids():
    if os.path.exists(TRANSLATED_IDS_FILE):
        with open(TRANSLATED_IDS_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_translated_ids(ids):
    with open(TRANSLATED_IDS_FILE, 'w') as f:
        json.dump(list(ids), f)

def parse_local_xml():
    if not os.path.exists(RAW_XML_FILE):
        print(f"[ERROR] Raw XML file '{RAW_XML_FILE}' does not exist.")
        return []

    pretty_print_xml(RAW_XML_FILE)

    try:
        context = ET.iterparse(RAW_XML_FILE, events=('end',))
        for event, elem in context:
            if elem.tag == 'Urun':
                yield elem
                elem.clear()
    except ET.ParseError as e:
        print(f"[ERROR] Failed to parse local XML: {e}")
    except Exception as e:
        print(f"[ERROR] Unexpected error parsing XML: {e}")

def process_and_save_translated_xml():
    usd_rate = get_exchange_rate()
    translated_ids = load_translated_ids()
    updated_ids = set(translated_ids)

    # Load existing output XML or create new
    if os.path.exists(OUTPUT_FILE):
        try:
            tree = ET.parse(OUTPUT_FILE)
            root_out = tree.getroot()
            urunler_out = root_out.find("Urunler")
            if urunler_out is None:
                urunler_out = ET.SubElement(root_out, "Urunler")
        except ET.ParseError as e:
            print(f"[ERROR] Failed to parse output XML: {e}")
            root_out = ET.Element("Root")
            urunler_out = ET.SubElement(root_out, "Urunler")
    else:
        root_out = ET.Element("Root")
        urunler_out = ET.SubElement(root_out, "Urunler")

    existing_barkods = set()
    for urun in urunler_out.findall("Urun"):
        for secenek in urun.findall(".//Secenek"):
            barkod = secenek.findtext("Barkod")
            if barkod:
                existing_barkods.add(barkod)

    new_root = ET.Element("Root")
    new_urunler = ET.SubElement(new_root, "Urunler")
    processed_count = 0

    for urun in parse_local_xml() or []:
        # Defensive: find VaryasyonID safely
        varyasyon_id = None
        urun_secenek = urun.find("UrunSecenek")
        if urun_secenek is not None:
            first_secenek = urun_secenek.find("Secenek")
            if first_secenek is not None:
                varyasyon_id = first_secenek.findtext("VaryasyonID")

        translate_this = varyasyon_id and varyasyon_id not in translated_ids

        barkods = [s.findtext("Barkod") for s in urun.findall(".//Secenek") if s.findtext("Barkod")]
        if any(b in existing_barkods for b in barkods):
            # Skip duplicates already in output
            continue

        updated_urun = ET.Element("Urun")

        for tag in urun:
            if tag.tag in ['UrunAdi', 'Aciklama', 'MateryalBileseni'] and translate_this:
                translated = translate_text(tag.text or '')
                ET.SubElement(updated_urun, tag.tag).text = translated
            else:
                ET.SubElement(updated_urun, tag.tag).text = tag.text

        if urun_secenek is not None:
            secenek_out = ET.SubElement(updated_urun, "UrunSecenek")
            for secenek in urun_secenek.findall("Secenek"):
                new_secenek = ET.SubElement(secenek_out, "Secenek")
                for s_tag in secenek:
                    if s_tag.tag in ["EkSecenekOzellik", "ozellik"] and translate_this:
                        translated_value = translate_text(s_tag.text or '')
                        ET.SubElement(new_secenek, s_tag.tag).text = translated_value
                    elif s_tag.tag == "SatisFiyati":
                        try:
                            price_try = float(s_tag.text)
                            price_usd = round(price_try * usd_rate, 2)
                            ET.SubElement(new_secenek, "SatisFiyati").text = str(price_usd)
                        except Exception:
                            ET.SubElement(new_secenek, "SatisFiyati").text = s_tag.text
                    else:
                        ET.SubElement(new_secenek, s_tag.tag).text = s_tag.text

        if translate_this and varyasyon_id:
            updated_ids.add(varyasyon_id)

        new_urunler.append(updated_urun)
        processed_count += 1

    if processed_count == 0:
        print("[WARNING] No new products processed. Skipping XML write to avoid empty output.")
        return

    # Append old untranslated products
    for urun in urunler_out.findall("Urun"):
        varyasyon_id = None
        urun_secenek = urun.find("UrunSecenek")
        if urun_secenek is not None:
            first_secenek = urun_secenek.find("Secenek")
            if first_secenek is not None:
                varyasyon_id = first_secenek.findtext("VaryasyonID")

        if varyasyon_id not in updated_ids:
            new_urunler.append(urun)

    tree_out = ET.ElementTree(new_root)
    tree_out.write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True)

    save_translated_ids(updated_ids)

if __name__ == "__main__":
    print(f"Started translation at {datetime.now().isoformat()}")
    process_and_save_translated_xml()
    print(f"Finished at {datetime.now().isoformat()}")
