# Code adapted from playwright-stealth
from playwright.async_api import Page

async def stealth_async(page: Page):
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)
    await page.add_init_script("""
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });
    """)
    await page.add_init_script("""
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
    """)
    await page.add_init_script("""
        window.chrome = {
            runtime: {}
        };
    """)
    await page.add_init_script("""
        Object.defineProperty(navigator, 'permissions', {
            get: () => ({
                query: Promise.resolve.bind(Promise.resolve, { state: 'granted' })
            })
        });
    """)

