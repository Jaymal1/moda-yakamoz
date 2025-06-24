from playwright.sync_api import sync_playwright

XML_URL = "https://modayakamoz.com/xml/yalin1"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    print("Navigating to the XML URL...")
    try:
        page.goto(XML_URL, timeout=1200000, wait_until="domcontentloaded")  # 20 minutes
        print("✅ Loaded! Saving content...")

        # Extract the real XML inside the <pre> tag or raw body text
        content = page.evaluate("document.body.innerText")

        with open("modayakamoz_raw.xml", "w", encoding="utf-8") as f:
            f.write(content.strip())

        print("✅ Saved to modayakamoz_raw.xml")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        browser.close()
