import xml.etree.ElementTree as ET
import os
import json
from datetime import datetime
from deep_translator import GoogleTranslator
import requests

# Constants
RAW_XML_FILE = "moda_raw.xml"
OUTPUT_FILE = "translatedsample_yakamoz.xml"
TRANSLATED_IDS_FILE = "translated_ids_yakamoz.json"
EXCHANGE_RATE_API = "https://api.exchangerate.host/latest?base=TRY&symbols=USD"

# Get exchange rate
def get_exchange_rate():
    try:
        res = requests.get(EXCHANGE_RATE_API, timeout=10)
        res.raise_for_status()
        return res.json()['rates']['USD']
    except Exception as e:
        print(f"[WARNING] Using fallback exchange rate due to error: {e}")
        return 0.031  # fallback default

# Translate text using Google Translator
def translate_text(text):
    try:
        return GoogleTranslator(source='tr', target='en').translate(text)
    except Exception as e:
        print(f"[WARNING] Translation failed: {e}")
        return text  # fallback: return original

# Load already translated products
def load_translated_ids():
    if os.path.exists(TRANSLATED_IDS_FILE):
        with open(TRANSLATED_IDS_FILE, 'r') as f:
            return set(json.load(f))
    return set()

# Save updated translated product IDs
def save_translated_ids(ids):
    with open(TRANSLATED_IDS_FILE, 'w') as f:
        json.dump(list(ids), f)

# Parse local XML file instead of fetching
def parse_local_xml():
    try:
        context = ET.iterparse(RAW_XML_FILE, events=('end',))
        for event, elem in context:
            if elem.tag == 'Urun':
                yield elem
                elem.clear()
    except Exception as e:
        print(f"[ERROR] Failed to parse local XML: {e}")
        return

# Main translation and sync function
def process_and_save_translated_xml():
    usd_rate = get_exchange_rate()
    translated_ids = load_translated_ids()
    updated_ids = set(translated_ids)

    # Load previous output if exists, else create root and Urunler element
    if os.path.exists(OUTPUT_FILE):
        tree = ET.parse(OUTPUT_FILE)
        root_out = tree.getroot()
        urunler_out = root_out.find("Urunler")
        if urunler_out is None:
            urunler_out = ET.SubElement(root_out, "Urunler")
    else:
        root_out = ET.Element("Root")
        urunler_out = ET.SubElement(root_out, "Urunler")

    # Collect existing Barkods to prevent duplicates
    existing_barkods = set()
    for urun in urunler_out.findall("Urun"):
        for secenek in urun.findall(".//Secenek"):
            barkod = secenek.findtext("Barkod")
            if barkod:
                existing_barkods.add(barkod)

    # Prepare new XML root and Urunler
    new_root = ET.Element("Root")
    new_urunler = ET.SubElement(new_root, "Urunler")

    processed_count = 0

    # Process new products from local XML
    for urun in parse_local_xml() or []:
        varyasyon_id = urun.findtext("UrunSecenek/Secenek/VaryasyonID")
        translate_this = varyasyon_id and varyasyon_id not in translated_ids

        barkods = [s.findtext("Barkod") for s in urun.findall(".//Secenek")]
        if any(b in existing_barkods for b in barkods):
            continue  # skip duplicates

        updated_urun = ET.Element("Urun")

        # Translate main tags
        for tag in urun:
            if tag.tag in ['UrunAdi', 'Aciklama', 'MateryalBileseni'] and translate_this:
                translated = translate_text(tag.text or '')
                ET.SubElement(updated_urun, tag.tag).text = translated
            else:
                ET.SubElement(updated_urun, tag.tag).text = tag.text

        # Translate Secenekler and convert price
        secenekler_in = urun.find("UrunSecenek")
        if secenekler_in is not None:
            secenek_out = ET.SubElement(updated_urun, "UrunSecenek")
            for secenek in secenekler_in.findall("Secenek"):
                new_secenek = ET.SubElement(secenek_out, "Secenek")
                for s_tag in secenek:
                    if s_tag.tag == "SatisFiyati":
                        try:
                            price_try = float(s_tag.text)
                            price_usd = round(price_try * usd_rate, 2)
                            ET.SubElement(new_secenek, "SatisFiyati").text = str(price_usd)
                        except:
                            ET.SubElement(new_secenek, "SatisFiyati").text = s_tag.text
                    else:
                        ET.SubElement(new_secenek, s_tag.tag).text = s_tag.text

        if translate_this:
            updated_ids.add(varyasyon_id)

        new_urunler.append(updated_urun)
        processed_count += 1

    if processed_count == 0:
        print("[WARNING] No new products processed. Skipping XML write to avoid empty output.")
        return

    # Append old products not updated
    for urun in urunler_out.findall("Urun"):
        varyasyon_id = urun.findtext("UrunSecenek/Secenek/VaryasyonID")
        if varyasyon_id not in updated_ids:
            new_urunler.append(urun)

    # Save final output
    tree_out = ET.ElementTree(new_root)
    tree_out.write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True)

    # Save updated translated IDs
    save_translated_ids(updated_ids)

if __name__ == "__main__":
    print(f"Started translation at {datetime.now().isoformat()}")
    process_and_save_translated_xml()
    print(f"Finished at {datetime.now().isoformat()}")
