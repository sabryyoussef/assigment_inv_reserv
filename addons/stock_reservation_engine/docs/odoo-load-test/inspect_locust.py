from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    p = b.new_page()
    p.goto('http://127.0.0.1:8089', wait_until='networkidle')
    stop = p.locator('button').filter(has_text='Stop')
    if stop.count(): stop.click(); p.wait_for_timeout(1000)
    new_btn = p.locator('button').filter(has_text='New')
    if new_btn.count(): new_btn.click(); p.wait_for_timeout(500)
    inputs = p.locator('input').all()
    for i in inputs:
        print('id:', i.get_attribute('id'), '| type:', i.get_attribute('type'), '| name:', i.get_attribute('name'), '| value:', i.input_value())
    b.close()
