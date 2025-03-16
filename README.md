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

Once the API is running, you can access the Swagger UI documentation at http://localhost:8000/docs.