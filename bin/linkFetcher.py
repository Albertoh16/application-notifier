import os
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

EMAIL = os.getenv("JOBRIGHT_EMAIL")
PASSWORD = os.getenv("JOBRIGHT_PASSWORD")

# This opens an invisible chromium-based browser.
def getBrowser(playwright):
    return playwright.chromium.launch(headless=True)

# This automatically navigates to jobright and logs into the pre-made account.
def loginToJobright(page, email, password):
    page.goto("https://jobright.ai/")
    
    # Clicks the sign in button.
    page.wait_for_selector("text=SIGN IN")
    page.click("text=SIGN IN")
    
    # Waits for the email input to appear.
    page.wait_for_selector("input[type='email'], input[name='email']")
    page.fill("input[type='email'], input[name='email']", email)
    page.fill("input[type='password']", password)
    page.click("button[type='submit']")
    
    # Waits until we're redirected to the dashboard.
    page.wait_for_url(lambda url: "jobright.ai" in url and url != "https://jobright.ai/", timeout=15000)
    time.sleep(2)

# this goes to the jobright application link, navigates the real application link, and returns the 
# actual job application URL.
def getApplicationURL(page, jobURL):
    page.goto(jobURL)
    page.wait_for_load_state("networkidle")

    try:
        applyButton = None

        selectors = [
            "text=Apply Now",
            "text=Apply on Employer Site",
            "a:has-text('Apply')",
            "button:has-text('Apply')",
        ]

        for selector in selectors:
            try:
                btn = page.locator(selector).first

                if btn.is_visible():
                    applyButton = btn
                    break
            except:
                continue

        if not applyButton:
            return jobURL

        context = page.context

        try:
            with context.expect_page(timeout=5000) as newPageInfo:
                applyButton.click()

            newPage = newPageInfo.value
            newPage.wait_for_load_state("load")
            jobrightURL = newPage.url
            newPage.close()

        except:
            time.sleep(2)

            jobrightURL = page.url

            if jobrightURL == jobURL:
                return jobURL
            
            page.go_back()

        return jobrightURL

    except Exception as e:
        return jobURL

# This fetches the actual application URL and replaces the jobright URL in the original listing.
def skipJobrightPage(jobs: dict) -> dict:
    with sync_playwright() as playwright:
        browser = getBrowser(playwright)
        context = browser.new_context()
        page = context.newPage()

        try:
            loginToJobright(page, EMAIL, PASSWORD)

            fixedJobs = {}

            for company, listings in jobs.items():
                fixedJobs[company] = []

                for (title, jobrightURL, location, workModel, industry, postDate) in listings:
                    realURL = getApplicationURL(page, jobrightURL)
                    fixedJobs[company].append((title, realURL, location, workModel, industry, postDate))
                    time.sleep(1)

            return fixedJobs

        except Exception as e:
            return jobs
        
        finally:
            browser.close()