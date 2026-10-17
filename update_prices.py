import json
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache"
}

COOKIES = {
    "country": "RU",
    "currency": "RUB",
    "site_locale": "ru"
}

def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()

def scrape_product_info(url: str):
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        session.cookies.update(COOKIES)

        res = session.get(url, timeout=15)
        if res.status_code != 200:
            return None, None

        html = res.text
        soup = BeautifulSoup(html, "html.parser")

        # 1. Поиск цены
        price = None
        
        # Проверка мета-тегов Schema / OpenGraph
        price_tag = soup.find("meta", property="product:price:amount") or soup.find("meta", itemprop="price")
        if price_tag and price_tag.get("content"):
            try:
                price = int(float(price_tag["content"]))
            except Exception:
                pass

        # Поиск через JSON-LD структуру
        if not price:
            for s in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(s.string)
                    if isinstance(data, dict):
                        offers = data.get("offers", {})
                        if isinstance(offers, dict) and "price" in offers:
                            price = int(float(offers["price"]))
                            break
                        elif isinstance(offers, list) and len(offers) > 0 and "price" in offers[0]:
                            price = int(float(offers[0]["price"]))
                            break
                except Exception:
                    continue

        # Регулярный поиск по тексту страницы (число + знак рубля)
        if not price:
            matches = re.findall(r"(\d+[\s\d]*)\s*(?:₽|руб\.?)", html, re.IGNORECASE)
            for m in matches:
                digits = int(re.sub(r"\D", "", m))
                if 100 <= digits <= 30000:
                    price = digits
                    break

        # 2. Поиск описания
        desc = None
        desc_tag = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
        if desc_tag and desc_tag.get("content"):
            content = clean_text(desc_tag["content"])
            if len(content) > 25 and "JavaScript" not in content and "Greenway Global" != content:
                desc = content

        return price, desc
    except Exception as e:
        print(f"Ошибка запроса {url}: {e}")
        return None, None

def main():
    try:
        with open("products.json", "r", encoding="utf-8") as f:
            products = json.load(f)
    except Exception as e:
        print(f"Не удалось открыть products.json: {e}")
        return

    updated_count = 0

    for item in products:
        url = item.get("gw_url")
        if not url or item.get("is_perfume_banner") or item.get("is_custom_request"):
            continue

        price, desc = scrape_product_info(url)
        changed = False

        if price and price != item.get("price"):
            print(f"[{item['title']}] Цена обновлена: {item.get('price')} -> {price} ₽")
            item["price"] = price
            changed = True

        if desc and desc != item.get("full_desc"):
            print(f"[{item['title']}] Описание обновлено.")
            item["full_desc"] = desc
            changed = True

        if changed:
            updated_count += 1

    if updated_count > 0:
        with open("products.json", "w", encoding="utf-8") as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        print(f"Успешно обновлено товаров: {updated_count}")
    else:
        print("Цены и описания полностью соответствуют сайту.")

if __name__ == "__main__":
    main()
