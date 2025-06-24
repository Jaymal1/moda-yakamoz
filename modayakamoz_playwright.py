from playwright.sync_api import sync_playwright

XML_URL = "https://modayakamoz.com/xml/yalin1"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    print("🌍 Navigating to the XML URL...")

    try:
        page.goto(XML_URL, timeout=1200000, wait_until="domcontentloaded")  # Wait up to 20 min
        print("✅ Page loaded. Extracting raw XML text...")

        # Only extract raw XML as string (avoid HTML parsing)
        content = page.evaluate("() => document.body.innerText")

        # Save to file
        with open("modayakamoz_raw.xml", "w", encoding="utf-8") as f:
            f.write(content)

        print("✅ XML saved to modayakamoz_raw.xml")

    except Exception as e:
        print(f"❌ Playwright error: {e}")

    finally:
        browser.close()
