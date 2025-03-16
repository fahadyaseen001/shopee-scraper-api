import os
import asyncio
import json
import random
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import stealth_async, StealthConfig
import uvicorn
import dotenv

from extension import SadCaptcha

# Load environment variables
dotenv.load_dotenv()

# Create FastAPI app
app = FastAPI(title="Shopee Product Scraper API", description="API for scraping Shopee product information")

# Input model
class ScrapingRequest(BaseModel):
    url: HttpUrl

# Response model
class ScrapingResponse(BaseModel):
    success: bool
    data: dict = None
    message: str = None
    
async def launch_browser_with_proxy(playwright):
    """Launch browser with the configured proxy"""
    
    # Get proxy configuration from environment variables
    proxy_config = None
    if os.getenv("CUSTOM_PROXY_SERVER"):
        proxy_config = {
            "server": os.getenv("CUSTOM_PROXY_SERVER"),
            "username": os.getenv("CUSTOM_PROXY_USERNAME"),
            "password": os.getenv("CUSTOM_PROXY_PASSWORD"),
        }
    
    # Initialize SadCaptcha extension
    extension_path = SadCaptcha(api_key=os.getenv("SADCAPTCHA_API_KEY")).load(with_command_line_option=False)
    
    print(f"Launching browser" + (f" with proxy: {proxy_config['server']}" if proxy_config else ""))
    
    browser = await playwright.chromium.launch_persistent_context(
        user_data_dir='.user_data',
        headless=False,
        proxy=proxy_config,
        args=[
            '--disable-extensions-except='+ extension_path,
            '--load-extension=' + extension_path,
            '--disable-blink-features=AutomationControlled'
        ],
        timeout=120000
    )
    
    page = await browser.new_page()
    
    # Apply anti-bot measures
    await page.add_init_script("delete Object.getPrototypeOf(navigator).webdriver")
    
    # Apply stealth configuration
    config = StealthConfig(
        navigator_languages=False,
        navigator_vendor=False,
        navigator_user_agent=False,
    )
    await stealth_async(page, config)
    
    return browser, page

async def scrape_product_data(page):
    """Scrape product information from the page"""
    product_data = {}
    
    # Get product title
    title_selectors = [
        '.pdp-mod-product-badge-title',
        '.product-title',
        'h1.pdp-title',
        'h1[data-testid="pdp-product-title"]',
        '.product-detail-panel__header__title'
    ]
    
    for selector in title_selectors:
        try:
            title_element = page.locator(selector)
            if await title_element.count() > 0:
                product_data['title'] = await title_element.text()
                print(f"Found product title: {product_data['title']}")
                break
        except Exception as e:
            pass
    
    # Get product price
    price_selectors = [
        '.pdp-price',
        '.product-price',
        '.pdp-mod-product-price',
        'div[data-testid="pdp-product-price"]',
        '.product-detail-panel__price'
    ]
    
    for selector in price_selectors:
        try:
            price_element = page.locator(selector)
            if await price_element.count() > 0:
                product_data['price'] = await price_element.text()
                print(f"Found product price: {product_data['price']}")
                break
        except Exception as e:
            pass
    
    # Get product description
    description_selectors = [
        '.pdp-product-desc',
        '.product-description',
        '.pdp-mod-product-desc',
        'div[data-testid="pdp-product-desc"]',
        '.product-detail-panel__description'
    ]
    
    for selector in description_selectors:
        try:
            desc_element = page.locator(selector)
            if await desc_element.count() > 0:
                product_data['description'] = await desc_element.text()
                print(f"Found product description (first 50 chars): {product_data['description'][:50]}...")
                break
        except Exception as e:
            pass
    
    # Get product images
    image_selectors = [
        '.pdp-mod-product-image img',
        '.product-image img',
        '.pdp-product-image img',
        'img[data-testid="pdp-product-image"]',
        '.product-detail-panel__image img'
    ]
    
    image_urls = []
    for selector in image_selectors:
        try:
            img_elements = page.locator(selector)
            count = await img_elements.count()
            if count > 0:
                for i in range(count):
                    img = img_elements.nth(i)
                    src = await img.get_attribute('src')
                    if src and src not in image_urls:
                        image_urls.append(src)
                
                product_data['image_urls'] = image_urls
                print(f"Found {len(image_urls)} product images")
                break
        except Exception as e:
            pass
    
    # Get seller information
    seller_selectors = [
        '.pdp-seller-info-name',
        '.product-seller-name',
        '.pdp-shop-name',
        'div[data-testid="pdp-shop-name"]',
        '.product-detail-panel__seller'
    ]
    
    for selector in seller_selectors:
        try:
            seller_element = page.locator(selector)
            if await seller_element.count() > 0:
                product_data['seller'] = await seller_element.text()
                print(f"Found seller: {product_data['seller']}")
                break
        except Exception as e:
            pass
    
    # Add the URL to the data
    product_data['url'] = page.url
    
    return product_data

@app.post("/scrape", response_model=ScrapingResponse)
async def scrape_shopee_product(request: ScrapingRequest):
    try:
        async with async_playwright() as p:
            browser, page = await launch_browser_with_proxy(p)
            
            try:
                # Go to the product URL
                print(f"Accessing URL: {request.url}")
                await page.goto(str(request.url), timeout=120000)
                
                # Wait for page to stabilize
                await page.wait_for_timeout(10000)
                
                # Check for captcha
                captcha_selectors = [
                    'div[id="New Captcha"]',
                    'div[id="captchaMask"]'
                ]
                
                captcha_found = False
                for selector in captcha_selectors:
                    try:
                        element = page.locator(selector)
                        if await element.count() > 0:
                            captcha_found = True
                            print(f"Captcha detected with selector: {selector}")
                            break
                    except Exception as e:
                        pass
                
                if captcha_found:
                    print("Captcha page displayed - waiting for captcha to solve...")
                    
                    # Set fixed wait time for captcha to solve
                    wait_time = 240000  # 4 minutes
                    print(f"Waiting for captcha to solve itself (4 minutes)...")
                    await page.wait_for_timeout(wait_time)
                    
                    # Check for captcha error messages after waiting
                    page_content = await page.content()
                    captcha_error_texts = [
                        "頁面無法顯示",
                        "發生錯誤！請返回再試一次或回到主頁",
                        "Page cannot be displayed",
                        "An error occurred! Please go back and try again or return to the homepage",
                        "驗證資訊失敗",
                        "抱歉，目前發生了一些錯誤。請下載並登入蝦皮購物 App 以繼續使用。",
                        "登出"
                    ]
                    
                    captcha_error_found = False
                    for error_text in captcha_error_texts:
                        if error_text in page_content:
                            captcha_error_found = True
                            print(f"Captcha error detected: '{error_text}'")
                            break
                    
                    if captcha_error_found:
                        await browser.close()
                        return ScrapingResponse(
                            success=False,
                            message="Captcha failed - received error page"
                        )
                    else:
                        print("Captcha solved successfully, proceeding to product page")
                
                # Wait for the product page to load
                await page.wait_for_timeout(5000)
                
                # Scrape product information
                product_data = await scrape_product_data(page)
                
                # Close the browser
                await browser.close()
                
                # Return the scraped data
                return ScrapingResponse(
                    success=True,
                    data=product_data,
                    message="Product data scraped successfully"
                )
                
            except PlaywrightTimeoutError:
                await browser.close()
                return ScrapingResponse(
                    success=False,
                    message="Timeout occurred while accessing the product page"
                )
                
            except Exception as e:
                await browser.close()
                return ScrapingResponse(
                    success=False,
                    message=f"Error during scraping: {str(e)}"
                )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True) 