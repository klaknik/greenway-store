import json
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
}

def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def scrape_product(url: str):
    try:
        response = requests.get(url, headers=HEADERS, timeout=12)
        if response.status_code != 200:
            return None, None
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 1. Извлечение цены
        price = None
        price_meta = soup.find("meta", property="product:price:amount")
        if price_meta and price_meta.get("content"):
            try:
                price = int(float(price_meta["content"]))
            except Exception:
                pass
        
        if not price:
            matches = soup.find_all(string=re.compile(r"(\d+[\s\d]*)\s*₽"))
            for m in matches:
                digits = re.sub(r"\D", "", m)
                if digits:
                    val = int(digits)
                    if 100 <= val <= 25000:
                        price = val
                        break

        # 2. Извлечение описания
        desc = None
        desc_meta = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
        if desc_meta and desc_meta.get("content"):
            content = clean_text(desc_meta["content"])
            if len(content) > 20:
                desc = content
                
        return price, desc
    except Exception as e:
        print(f"Ошибка при запросе {url}: {e}")
        return None, None

def main():
    try:
        with open("products.json", "r", encoding="utf-8") as f:
            products = json.load(f)
    except Exception as e:
        print(f"Не удалось прочесть products.json: {e}")
        return

    updated_count = 0

    for item in products:
        url = item.get("gw_url")
        if not url:
            continue

        price, desc = scrape_product(url)
        changed = False

        if price and price != item.get("price"):
            print(f"[{item['title']}] Цена обновлена: {item.get('price')} -> {price} ₽")
            item["price"] = price
            changed = True

        if desc and len(desc) > 30 and desc != item.get("full_desc"):
            print(f"[{item['title']}] Описание обновлено.")
            item["full_desc"] = desc
            changed = True

        if changed:
            updated_count += 1

    if updated_count > 0:
        with open("products.json", "w", encoding="utf-8") as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        print(f"Успешно обновлено позиций: {updated_count}")
    else:
        print("Все цены и описания актуальны. Изменений не требуется.")

if __name__ == "__main__":
    main()
