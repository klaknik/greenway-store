import json
import re
import asyncio
from playwright.async_api import async_playwright

async def get_product_data(context, url):
    page = await context.new_page()
    captured_data = {}

    # Перехватываем API-ответы бэкенда Greenway
    async def handle_response(response):
        try:
            if "api" in response.url and ("product" in response.url or "item" in response.url):
                data = await response.json()
                if isinstance(data, dict):
                    # Ищем цену и описание в структуре ответа
                    if "price" in data:
                        captured_data["price"] = int(float(data["price"]))
                    elif "data" in data and isinstance(data["data"], dict) and "price" in data["data"]:
                        captured_data["price"] = int(float(data["data"]["price"]))
                    if "description" in data:
                        captured_data["desc"] = data["description"]
        except Exception:
            pass

    page.on("response", handle_response)

    try:
        # Устанавливаем куку региона Россия (чтобы цены были строго в рублях)
        await context.add_cookies([
            {"name": "country", "value": "RU", "domain": ".greenwayglobal.com", "path": "/"},
            {"name": "currency", "value": "RUB", "domain": ".greenwayglobal.com", "path": "/"}
        ])

        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3500)

        price = captured_data.get("price")
        desc = captured_data.get("desc")

        # Если через API не перехватилось — считываем со страницы
        if not price:
            content = await page.content()
            # Поиск блоков с ценой в рублях
            rub_matches = re.findall(r"(\d+[\s\d]*)\s*(?:₽|руб)", content, re.IGNORECASE)
            for m in rub_matches:
                digits = int(re.sub(r"\D", "", m))
                if 120 <= digits <= 30000:
                    price = digits
                    break

        if not desc:
            meta = await page.locator('meta[name="description"]').get_attribute('content')
            if meta and len(meta.strip()) > 30 and "JavaScript" not in meta:
                desc = re.sub(r"\s+", " ", meta).strip()

        await page.close()
        return price, desc
    except Exception as e:
        print(f"Ошибка при обработке {url}: {e}")
        await page.close()
        return None, None

async def main():
    try:
        with open("products.json", "r", encoding="utf-8") as f:
            products = json.load(f)
    except Exception as e:
        print(f"Ошибка чтения products.json: {e}")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="ru-RU",
            viewport={"width": 1280, "height": 800}
        )

        updated_count = 0
        for item in products:
            url = item.get("gw_url")
            if not url or item.get("is_perfume_banner") or item.get("is_custom_request"):
                continue

            price, desc = await get_product_data(context, url)
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

            # Пауза между товарами, чтобы сервер не заподозрил бота
            await asyncio.sleep(1)

        await browser.close()

    if updated_count > 0:
        with open("products.json", "w", encoding="utf-8") as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        print(f"Успешно сохранено изменений: {updated_count}")
    else:
        print("Цены проверены, расхождений не найдено.")

if __name__ == "__main__":
    asyncio.run(main())
