import xml.etree.ElementTree as ET
import requests
import os
import json
from datetime import datetime
from deep_translator import GoogleTranslator

# Constants
XML_URL = "https://modayakamoz.com/xml/yalin1"
OUTPUT_FILE = "translatedsample_yakamoz.xml"
TRANSLATED_IDS_FILE = "translated_ids_yakamoz.json"
EXCHANGE_RATE_API = "https://api.exchangerate.host/latest?base=TRY&symbols=USD"

# Get exchange rate
def get_exchange_rate():
    try:
        res = requests.get(EXCHANGE_RATE_API)
        res.raise_for_status()
        return res.json()['rates']['USD']
    except:
        return 0.031  # fallback default

# Translate text using Google Translator
def translate_text(text):
    try:
        return GoogleTranslator(source='tr', target='en').translate(text)
    except:
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

# Parse large XML efficiently
def parse_large_xml():
    response = requests.get(XML_URL, stream=True)
    response.raise_for_status()
    for event, elem in ET.iterparse(response.raw, events=('end',)):
        if elem.tag == 'Urun':
            yield elem
            elem.clear()

# Main translation and sync function
def process_and_save_translated_xml():
    usd_rate = get_exchange_rate()
    translated_ids = load_translated_ids()
    updated_ids = set(translated_ids)

    # Load previous output if exists
    if os.path.exists(OUTPUT_FILE):
        tree = ET.parse(OUTPUT_FILE)
        root_out = tree.getroot()
    else:
        root_out = ET.Element("Root")
        urunler_out = ET.SubElement(root_out, "Urunler")

    # Use dictionary for quick lookup by Barkod
    existing_products = {}
    for urun in root_out.find("Urunler") or []:
        for secenek in urun.findall(".//Secenek"):
            barkod = secenek.findtext("Barkod")
            if barkod:
                existing_products[barkod] = urun

    # Prepare new output tree
    new_root = ET.Element("Root")
    new_urunler = ET.SubElement(new_root, "Urunler")

    for urun in parse_large_xml():
        updated_urun = ET.Element("Urun")
        varyasyon_id = urun.findtext("UrunSecenek/Secenek/VaryasyonID")
        translate_this = varyasyon_id not in translated_ids

        # Translate general product fields if new
        for tag in urun:
            if tag.tag in ['UrunAdi', 'Aciklama', 'MateryalBileseni'] and translate_this:
                translated = translate_text(tag.text or '')
                ET.SubElement(updated_urun, tag.tag).text = translated
            else:
                ET.SubElement(updated_urun, tag.tag).text = tag.text

        # Process each Secenek
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
                    elif s_tag.tag == "StokAdedi":
                        ET.SubElement(new_secenek, "StokAdedi").text = s_tag.text
                    else:
                        ET.SubElement(new_secenek, s_tag.tag).text = s_tag.text

        # Update translated ID list
        if translate_this:
            updated_ids.add(varyasyon_id)

        # Remove duplicates
        barkods = [s.findtext("Barkod") for s in urun.findall(".//Secenek")]
        existing = any(barkod in existing_products for barkod in barkods)
        if not existing:
            new_urunler.append(updated_urun)

    # Append old unchanged data
    if os.path.exists(OUTPUT_FILE):
        for urun in root_out.find("Urunler"):
            varyasyon_id = urun.findtext("UrunSecenek/Secenek/VaryasyonID")
            if varyasyon_id not in updated_ids:
                new_urunler.append(urun)

    # Write to output
    tree_out = ET.ElementTree(new_root)
    tree_out.write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True)

    # Save updated translated IDs
    save_translated_ids(updated_ids)

if __name__ == "__main__":
    print(f"Started translation at {datetime.now().isoformat()}")
    process_and_save_translated_xml()
    print(f"Finished at {datetime.now().isoformat()}")

