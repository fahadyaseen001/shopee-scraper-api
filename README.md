# Shopee Product Scraper API

An API for scraping product information from Shopee Taiwan.

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
   - Copy `.env.example` to `.env`
   - Fill in your credentials and configuration in the `.env` file

## Running the API

```bash
cd app
python api.py
```

This will start the API server at http://localhost:8000.

## API Endpoints

### POST /scrape

Scrapes product information from a Shopee product URL.

**Request Body:**
```json
{
  "url": "https://shopee.tw/product-url"
}
```

- `url`: The Shopee product URL to scrape

**Response:**
```json
{
  "success": true,
  "data": {
    "title": "Product Title",
    "price": "Product Price",
    "description": "Product Description",
    "image_urls": ["url1", "url2", ...],
    "seller": "Seller Name",
    "url": "Product URL"
  },
  "message": "Product data scraped successfully"
}
```

## Documentation

### Key Features

#### Shopee Captcha Handling
- Uses SadCaptcha extension to automatically handle Shopee's captcha challenges
- Waits for captchas to be solved (4-minute timeout)
- Detects and reports captcha failures with specific error messages
- Continues scraping automatically after successful captcha solving

#### Anti-Detection Measures
- Successfully passes all checks on BotSammy, confirming its effectiveness in bypassing bot detection
- Implements Playwright stealth mode to avoid bot detection
- Uses anti-bot techniques like webdriver attribute removal
- Configures browser settings to appear as legitimate human traffic

#### Proxy Rotation Support
- Supports custom HTTP/HTTPS proxies for accessing Shopee
- Configurations can be set via environment variables
- Helps bypass IP-based rate limits and geographic restrictions

#### Resilient Scraping
- Uses multiple selector patterns to find product information
- Adapts to different Shopee page layouts and structures
- Handles various error scenarios gracefully

### Usage Examples

#### CURL Example
```bash
curl -X POST "http://localhost:8000/scrape" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://shopee.tw/product-example-i.12345.67890"}'
```

### Performance Considerations

- The API uses a headful browser which requires more resources than headless scraping
- Each scraping request takes approximately 30-60 seconds to complete (longer if captcha appears)
- For production use, consider implementing a request queue system
- The API is designed for accuracy and reliability, not high-volume scraping

### Troubleshooting

- **Captcha Issues**: If captchas consistently fail, try using different proxies
- **Connection Errors**: Ensure your proxy settings are correct and the proxy is operational
- **Missing Data**: Some product pages may have different layouts - create an issue if scraping fails
- **API Crashes**: Check if you have sufficient memory, as browser automation requires significant resources
- **Timeout Problems**: 
  - If requests timeout frequently, check your network stability
  - For slow-loading pages, increase the timeout value in the code (currently set to 120s for navigation)
  - Timeouts during captcha waiting period (4 minutes) often indicate blocking or network issues
  - Consider using higher quality proxies if timeouts persist