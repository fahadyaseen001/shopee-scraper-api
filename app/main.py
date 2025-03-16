import os
import dotenv
import asyncio
import re
import json
import random
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Page
from playwright_stealth import stealth_async, StealthConfig

from extension import SadCaptcha

dotenv.load_dotenv()

# Get Google credentials from environment variables
GOOGLE_EMAIL = os.getenv("GOOGLE_EMAIL")
GOOGLE_PASSWORD = os.getenv("GOOGLE_PASSWORD")

class ProxyRotator:
    def __init__(self):
        self.proxies = self._load_proxies_from_env()
        self.tried_proxies = set()
        
    def _load_proxies_from_env(self):
        proxies = []
        
        # Add CUSTOM_PROXY
        if os.getenv("CUSTOM_PROXY_SERVER"):
            proxies.append({
                "server": os.getenv("CUSTOM_PROXY_SERVER"),
                "username": os.getenv("CUSTOM_PROXY_USERNAME"),
                "password": os.getenv("CUSTOM_PROXY_PASSWORD"),
            })
        
        # Add GEONODE_PROXY
        if os.getenv("GEONODE_PROXY_SERVER"):
            proxies.append({
                "server": os.getenv("GEONODE_PROXY_SERVER"),
                "username": os.getenv("GEONODE_PROXY_USERNAME"),
                "password": os.getenv("GEONODE_PROXY_PASSWORD"),
            })
        
        # Add additional numbered proxies
        for i in range(1, 10):  # Support up to 10 numbered proxies
            prefix = f"GEONODE_PROXY_{i}"
            if os.getenv(f"{prefix}_SERVER"):
                proxies.append({
                    "server": os.getenv(f"{prefix}_SERVER"),
                    "username": os.getenv(f"{prefix}_USERNAME"),
                    "password": os.getenv(f"{prefix}_PASSWORD"),
                })
        
        return proxies
    
    def get_random_proxy(self):
        """Get a random proxy that hasn't been tried yet in this cycle"""
        if not self.proxies:
            return None
            
        # If all proxies have been tried, reset the tried_proxies set
        if len(self.tried_proxies) >= len(self.proxies):
            self.tried_proxies = set()
            
        # Get available proxies (those not tried yet)
        available_proxies = [p for i, p in enumerate(self.proxies) 
                             if p["server"] not in self.tried_proxies]
                             
        # If no available proxies (shouldn't happen due to reset above, but just in case)
        if not available_proxies:
            self.tried_proxies = set()
            available_proxies = self.proxies
            
        # Select a random proxy from available ones
        proxy = random.choice(available_proxies)
        self.tried_proxies.add(proxy["server"])
        
        return proxy


async def is_shopee_blocking(page):
    """Enhanced check if Shopee is blocking us"""
    try:
        # Check for common blocking indicators
        current_url = page.url
        
        # Check if page is blank (no content)
        page_content = await page.content()
        if len(page_content.strip()) < 100 and "shopee" in current_url:
            print("Detected blank or nearly blank page - possible blocking")
            return True
            
        # Check for specific error messages in the content
        block_indicators = [
            # First block indicator
            "驗證資訊失敗",
            "抱歉，我們無法驗證資訊，請稍等並再試一次。",
            "再試一次",
            
            # Second block indicator
            "請登入蝦皮購物 App",
            "抱歉，目前發生了一些錯誤。請下載並登入蝦皮購物 App 以繼續使用。",
            "登出"
        ]
        
        for indicator in block_indicators:
            if indicator in page_content:
                print(f"Detected blocking indicator: {indicator}")
                return True
        
        # Check for expected content elements that should be present (Google sign-in button)
        google_button_selectors = [
            'button:has-text("Google")', 
            '.google-login',
            '.social-white-google-png',
            '.social-login svg[title="Google"]',
            'div[aria-label="Continue with Google"]',
            'img[alt*="Google"]',
            'a[href*="accounts.google.com"]'
        ]
        
        found_expected_element = False
        for selector in google_button_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    found_expected_element = True
                    break
            except:
                pass
        
        if not found_expected_element and "shopee" in current_url:
            print("Google sign-in button not found - possible blocking")
            return True
        
        # Check response status codes from navigation
        if hasattr(page, 'last_response') and page.last_response:
            status = page.last_response.status
            if status >= 400:
                print(f"Received error status code: {status}")
                return True
            
        return False
    except Exception as e:
        print(f"Error checking if blocked: {str(e)}")
        return True  # Assume blocked if there's an error


async def handle_google_login_process(page, popup_page):
    """Handle the Google login popup process"""
    try:
        # Wait for Google login page to load with random delay
        await popup_page.wait_for_timeout(random.randint(2000, 4000))
        
        
        # If credentials not provided, manual login is required
        if not GOOGLE_EMAIL or not GOOGLE_PASSWORD:
            print("Google credentials not provided in .env file")
            print("Please login manually in the popup window")
            # Wait for manual login
            await popup_page.wait_for_timeout(120000)
            return False
        
        # Enter email with random typing delays
        try:
            await popup_page.wait_for_selector('input[type="email"]', timeout=10000)
            print("Email field found")
            
            # Type email with random delays between keystrokes
            email_input = popup_page.locator('input[type="email"]')
            await email_input.click()
            
            for char in GOOGLE_EMAIL:
                await email_input.type(char, delay=random.randint(100, 300))
                await popup_page.wait_for_timeout(random.randint(10, 50))
            
            print(f"Entered email: {GOOGLE_EMAIL}")
            
            # Random delay before clicking next
            await popup_page.wait_for_timeout(random.randint(800, 1500))
            
            # Click next button - try different selectors
            next_button_selectors = [
                'div[id="identifierNext"]',
                'button:has-text("Next")',
                '//div[contains(text(), "Next")]'
            ]
            
            for selector in next_button_selectors:
                try:
                    next_button = popup_page.locator(selector)
                    if await next_button.count() > 0:
                        await next_button.click()
                        print(f"Clicked Next after email using selector: {selector}")

                        break
                
                except Exception as e:
                    print(f"Failed to click next with selector {selector}: {str(e)}")

            
            # Wait for password field to appear with random delay
            await popup_page.wait_for_timeout(random.randint(2000, 4000))
            
  
            # Enter password with random typing delays
            try:
                # Try different password field selectors
                password_selectors = [
                    'input[type="password"][name="password"]',
                    'input[aria-label="Enter your password"]',
                    'input[type="password"]'
                ]
                
                password_field = None
                for selector in password_selectors:
                    field = popup_page.locator(selector)
                    if await field.count() > 0:
                        password_field = field
                        print(f"Found password field with selector: {selector}")
                        break
                
                if password_field:
                    await password_field.click()
                    
                    # Type password with random delays between keystrokes
                    for char in GOOGLE_PASSWORD:
                        await password_field.type(char, delay=random.randint(100, 300))
                        await popup_page.wait_for_timeout(random.randint(10, 50))
                    
                    print("Password entered")
                    
                    # Random delay before clicking next
                    await popup_page.wait_for_timeout(random.randint(800, 1500))
                    
                    # Click the password next button
                    password_next_selectors = [
                        'div[id="passwordNext"]',
                        'button:has-text("Next")',
                        '//div[contains(text(), "Next")]'
                    ]
                    
                    for selector in password_next_selectors:
                        try:
                            next_button = popup_page.locator(selector)
                            if await next_button.count() > 0:
                                await next_button.click()
                                print(f"Clicked Next after password using selector: {selector}")
                                break
                        except Exception as e:
                            print(f"Failed to click password next with selector {selector}: {str(e)}")
                else:
                    print("Password field not found")
                    return False
                
                # Wait for consent screen with random delay
                await popup_page.wait_for_timeout(random.randint(2000, 3000))
                
                # Handle consent screen with an even simpler approach
                try:
                    print("Looking for consent buttons...")
                    
                    # Define selectors for consent buttons
                    # consent_selectors = [
                    #     'button:has-text("Continue")',
                    #     'button:has-text("繼續")',
                    #     '[role="button"]:has-text("Continue")',
                    #     'div[role="button"]:has-text("Continue")',
                    #     'div[jsname="Njthtb"]'
                    # ]
                    
                    # Check if any consent button is present in the page without using locators
                    consent_js = '''
                    () => {
                      const selectors = [
                        'button:has-text("Continue")',
                        'button:has-text("繼續")',
                        '[role="button"]:has-text("Continue")',
                        'div[role="button"]:has-text("Continue")',
                        'div[jsname="Njthtb"]',
                        'button[jsname="LgbsSe"]'
                      ];
                      
                      for (const selector of selectors) {
                        try {
                          const element = document.querySelector(selector);
                          if (element) {
                            console.log('Found consent button:', selector);
                            element.click();
                            return true;
                          }
                        } catch (e) {
                          console.error('Error with selector:', selector, e);
                        }
                      }
                      return false;
                    }
                    '''
                    
                    # Execute the JavaScript to find and click any consent button
                    clicked = await popup_page.evaluate(consent_js)
                    if clicked:
                        print("Successfully clicked a consent button via JavaScript")
                    else:
                        print("No consent buttons found via JavaScript")
                    
                    # Wait for any navigation to complete
                    await popup_page.wait_for_timeout(5000)
                    print("Consent handling completed")
                    return True
                    
                except Exception as consent_error:
                    print(f"Error during consent handling: {str(consent_error)}")
                    # Take a screenshot for debugging
                    try:
                        await popup_page.screenshot(path="consent_error.png")
                    except:
                        pass
                    
                    # Still continue as the login may have succeeded
                    return True
                
            except Exception as e:
                print(f"Error during password entry: {str(e)}")
                return False
                
        except Exception as e:
            print(f"Error during email entry: {str(e)}")
            return False
            
    except Exception as e:
        print(f"Google login popup handling failed: {str(e)}")
        try:
            await popup_page.screenshot(path="login_error.png")
        except:
            pass
        return False


async def launch_browser_with_proxy(playwright, extension_path, proxy_config):
    """Launch browser with the given proxy configuration"""
    print(f"Launching browser with proxy: {proxy_config['server']}")
    
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
    
    # Store the navigation response for later status code checking
    page.last_response = None
    page.route("**", lambda route, request: handle_route(route, request, page))
    
    return browser, page


async def handle_route(route, request, page):
    # Continue the request normally
    response = await route.continue_()
    # Store the last response for the main document
    if request.resource_type == "document":
        page.last_response = response
    return response


async def main():
    try:
        # Initialize proxy rotator
        proxy_rotator = ProxyRotator()
        if not proxy_rotator.proxies:
            print("No proxies found in environment variables!")
            return
        
        print(f"Loaded {len(proxy_rotator.proxies)} proxies")
        
        # Initialize SadCaptcha extension
        extension_path = SadCaptcha(api_key=os.getenv("SADCAPTCHA_API_KEY")).load(with_command_line_option=False)
        
        async with async_playwright() as p:
            # Run indefinitely, cycling through proxies
            attempts = 0
            max_attempts_before_break = 10  # Safety limit to prevent infinite loops
            success = False
            
            while not success and attempts < max_attempts_before_break:
                proxy_config = proxy_rotator.get_random_proxy()
                attempts += 1
                
                print(f"\n--- Attempt {attempts} with proxy {proxy_config['server']} ---")
                
                try:
                    browser, page = await launch_browser_with_proxy(p, extension_path, proxy_config)
                    
                    # Go directly to Shopee
                    print("Accessing Shopee...")
                    await page.goto("https://shopee.tw/---i.31188538.19323502897", timeout=120000)
                    
                    # Wait for page to stabilize
                    await page.wait_for_timeout(10000)
                    
                    # Check if we're blocked
                    if await is_shopee_blocking(page):
                        print("Shopee is blocking this proxy, switching to next...")
                        await browser.close()
                        continue  # Will automatically get a new random proxy next loop
                    
                    # If we get here, we've successfully accessed Shopee
                    print("Successfully accessed Shopee!")
                    
                    
                    # Check if there's a language selection dialog and handle it
                    try:
                        language_selector = page.locator('button:has-text("繁體中文")')
                        if await language_selector.count() > 0:
                            await language_selector.click()
                            print("Selected language: Traditional Chinese")
                            await page.wait_for_timeout(1000)
                    except Exception as e:
                        print(f"Language selection not found or not needed: {str(e)}")
                    
                    # Find the Google login button on the page we're already on
                    google_button_selectors = [
                        'button:has-text("Google")', 
                        '.google-login',
                        '.social-white-google-png',
                        '.social-login svg[title="Google"]',
                        'div[aria-label="Continue with Google"]',
                        'img[alt*="Google"]',
                        'a[href*="accounts.google.com"]'
                    ]
                    
                    # Add random delay to simulate human behavior
                    await page.wait_for_timeout(random.randint(1000, 3000))
                    
                    # Find the Google button
                    google_button = None
                    for selector in google_button_selectors:
                        button = page.locator(selector)
                        if await button.count() > 0:
                            google_button = button
                            print(f"Found Google login button with selector: {selector}")
                            break
                            
                    if not google_button:
                        print("Google login button not found on current page")
                        
                        # Try again with another proxy
                        await browser.close()
                        continue
                    
                    # Handle popup window for Google login
                    login_success = False
                    try:
                        print("Clicking Google login button and waiting for popup...")
                        # Random delay before clicking
                        await page.wait_for_timeout(random.randint(500, 1500))
                        
                        # Click the button and wait for popup
                        async with page.expect_popup(timeout=60000) as popup_info:
                            await google_button.click()
                            
                        # Get popup page with Google login
                        popup_page = await popup_info.value
                        print("Google login popup opened")
                        
                        # Handle the Google login popup process
                        login_popup_success = await handle_google_login_process(page, popup_page)
                        
                        if login_popup_success:
                            # Wait for redirection back to Shopee after successful login
                            await page.wait_for_timeout(random.randint(5000, 8000))
                            
                            # Verify if login was successful
                            
                            print(f"Current URL after login attempt: {page.url}")
    
                            # Check for different post-login scenarios
                            page_content = await page.content()
                            
                            # 1. Check for captcha page - this is a positive case
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
                                print("Successfully logged in - captcha page displayed")
                                login_success = True
                                
                                # Save and mark this as a captcha success
                                with open(f"captcha_success_{attempts}.txt", "w") as f:
                                    f.write(f"Captcha found with proxy: {proxy_config['server']}")
                                
                                # Wait for captcha to solve itself (up to 4 minutes)
                                print("Waiting for captcha to solve itself (up to 4 minutes)...")
                                await page.wait_for_timeout(240000)  # 4 minutes = 240000ms
                                
                                # After waiting, check current URL and page content
                                current_url = page.url
                                page_content = await page.content()
                                print(f"URL after captcha wait: {current_url}")
                                
                                # Check for captcha error messages
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
                                    print("Captcha failed - received error page")
                                    login_success = False
                                    
                                    # Save for debugging
                                    with open(f"captcha_error_{attempts}.txt", "w") as f:
                                        f.write(f"Captcha error with proxy: {proxy_config['server']}")
                                    
                                    # Take a screenshot of the error page
                                    await page.screenshot(path=f"captcha_error_{attempts}.png")
                                    
                                    # Try again with another proxy
                                    await browser.close()
                                    continue
                                else:
                                    print("Captcha solved successfully, proceeding to product page")
                                    
                                    # Wait for the product page to load
                                    await page.wait_for_timeout(5000)
                                    
                                    # Scrape product information
                                    print("Scraping product information...")
                                    
                                    try:
                                        # Extract product data
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
                                        
                                        # Take a screenshot of the product page
                                        await page.screenshot(path=f"product_page_{attempts}.png")
                                        
                                        # Save the scraped data
                                        product_data['url'] = page.url
                                        product_data['timestamp'] = asyncio.get_event_loop().time()
                                        product_data['proxy_used'] = proxy_config['server']
                                        
                                        with open(f"product_data_{attempts}.json", "w", encoding="utf-8") as f:
                                            json.dump(product_data, f, indent=2, ensure_ascii=False)
                                        
                                        print(f"Successfully scraped product data and saved to product_data_{attempts}.json")
                                        
                                    except Exception as scrape_error:
                                        print(f"Error scraping product data: {str(scrape_error)}")
                                        # Continue with the flow even if scraping fails
                            
                            # 2. Check for app-only error page - this is a negative case
                            app_only_error_texts = [
                                "Please log in to Shopee Shopping App",
                                "Sorry, some errors have occurred",
                                "請登入蝦皮購物 App",
                                "抱歉，目前發生了一些錯誤"
                            ]
                            
                            app_error_found = False
                            for error_text in app_only_error_texts:
                                if error_text in page_content:
                                    app_error_found = True
                                    print(f"App-only error detected: '{error_text}'")
                                    break
                                    
                            if app_error_found:
                                print("Login failed - received app-only error page")
                                login_success = False
                                
                                # Save for debugging
                                with open(f"app_error_{attempts}.txt", "w") as f:
                                    f.write(f"App error with proxy: {proxy_config['server']}")
                                
                                # Try again with another proxy
                                await browser.close()
                                continue
                            
                            # 3. Check for blank page - this is also a negative case
                            if len(page_content.strip()) < 200:  # Increased threshold to catch nearly blank pages
                                print("Login failed - received blank or nearly blank page")
                                login_success = False
                                
                                # Save for debugging
                                with open(f"blank_page_{attempts}.txt", "w") as f:
                                    f.write(f"Blank page with proxy: {proxy_config['server']}")
                                    
                                # Try again with another proxy
                                await browser.close()
                                continue
                            
                    except Exception as e:
                        print(f"Error during Google login process: {str(e)}")
                        await page.screenshot(path=f"login_error_{attempts}.png")
                        # Try again with another proxy
                        await browser.close()
                        continue
                    
                    if login_success:
                        print("Google login process completed successfully")
                        
                        # Save successful result information
                        try:
                            success_info = {
                                "proxy": proxy_config["server"],
                                "time": asyncio.get_event_loop().time(),
                                "url": page.url,
                                "title": await page.title(),
                                "login_status": "success",
                                "captcha_found": captcha_found,
                            }
                            with open("successful_access.json", "w") as f:
                                json.dump(success_info, f, indent=2)
                        except Exception as e:
                            print(f"Error saving success info: {str(e)}")
                        
                        success = True
                        await page.wait_for_timeout(30000)  # Keep the page open for 30 seconds
                    else:
                        print("Google login failed, trying another proxy...")
                        
                    await browser.close()
                    
                except PlaywrightTimeoutError:
                    print("Timeout occurred, switching to next proxy...")
                    try:
                        await page.screenshot(path=f"timeout_{attempts}.png")
                    except:
                        pass
                    await browser.close()
                
                except Exception as e:
                    print(f"Error with current proxy: {str(e)}")
                    try:
                        await page.screenshot(path=f"error_{attempts}.png")
                    except:
                        pass
                    await browser.close()
            
            if success:
                print(f"Successfully accessed Shopee and logged in after {attempts} attempts")
            else:
                print(f"Failed to access Shopee or login after {attempts} attempts. Consider adding more proxies.")
                
    except Exception as e:
        print(f"Critical error: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
