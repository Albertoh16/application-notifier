import os
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

EMAIL = os.getenv("JOBRIGHT_EMAIL")
PASSWORD = os.getenv("JOBRIGHT_PASSWORD")


# This opens an invisible chromium-based browser.
def getBrowser(playwright):
    print("[DEBUG] Launching headless Chromium...")
    return playwright.chromium.launch(headless=True)


# This automatically navigates to jobright and logs into the pre-made account.
def loginToJobright(page, email, password):
    print(f"[DEBUG] Navigating to https://jobright.ai/...")
    page.goto("https://jobright.ai/")
    print(f"[DEBUG] Current URL after goto: {page.url}")

    print("[DEBUG] Waiting for SIGN IN button...")
    page.wait_for_selector("text=SIGN IN", timeout=10000)
    print("[DEBUG] Clicking SIGN IN button...")
    page.click("text=SIGN IN")

    print("[DEBUG] Waiting for email input in modal...")
    page.wait_for_selector("input[type='email'], input[name='email']", timeout=10000)
    print("[DEBUG] Filling email...")
    page.fill("input[type='email'], input[name='email']", email)

    print("[DEBUG] Filling password...")
    page.fill("input[type='password']", password)

    print("[DEBUG] Clicking submit...")
    page.click("button[type='submit']")

    print("[DEBUG] Waiting for redirect after login...")
    page.wait_for_url(lambda url: "jobright.ai" in url and url != "https://jobright.ai/", timeout=15000)
    print(f"[DEBUG] Login successful! Current URL: {page.url}")
    time.sleep(2)


def getApplicationURL(page, jobURL):
    print(f"\n[DEBUG] Navigating to job URL: {jobURL}")
    page.goto(jobURL)
    page.wait_for_load_state("networkidle")
    print(f"[DEBUG] Page loaded. Current URL: {page.url}")

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
                    print(f"[DEBUG] Found apply button with selector: '{selector}'")
                    applyButton = btn
                    break
                else:
                    print(f"[DEBUG] Selector '{selector}' found but not visible")
            except Exception as e:
                print(f"[DEBUG] Selector '{selector}' failed: {e}")
                continue

        if not applyButton:
            print(f"[DEBUG] No apply button found on {jobURL}, returning original URL")
            return jobURL

        context = page.context

        try:
            print("[DEBUG] Clicking apply button, waiting for new tab...")
            with context.expect_page(timeout=5000) as newPageInfo:
                applyButton.click()

            newPage = newPageInfo.value
            newPage.wait_for_load_state("load")
            realURL = newPage.url
            print(f"[DEBUG] New tab opened with URL: {realURL}")
            newPage.close()

        except Exception as e:
            print(f"[DEBUG] No new tab opened ({e}), checking for same-tab redirect...")
            time.sleep(2)
            realURL = page.url
            print(f"[DEBUG] Current URL after click: {realURL}")

            if realURL == jobURL:
                print(f"[DEBUG] URL unchanged, returning original")
                return jobURL

            page.go_back()

        print(f"[DEBUG] Resolved URL: {realURL}")
        return realURL

    except Exception as e:
        print(f"[DEBUG] Exception in getApplicationURL: {e}")
        return jobURL


# This fetches the actual application URL and replaces the jobright URL in the original listing.
def skipJobrightPage(jobs: dict) -> dict:
    print(f"\n[DEBUG] skipJobrightPage called with {sum(len(v) for v in jobs.values())} total jobs across {len(jobs)} companies")
    print(f"[DEBUG] EMAIL loaded: {'yes' if EMAIL else 'NO - CHECK SECRETS'}")
    print(f"[DEBUG] PASSWORD loaded: {'yes' if PASSWORD else 'NO - CHECK SECRETS'}")

    with sync_playwright() as playwright:
        browser = getBrowser(playwright)
        context = browser.new_context()
        page = context.new_page()

        try:
            loginToJobright(page, EMAIL, PASSWORD)

            fixedJobs = {}

            for company, listings in jobs.items():
                print(f"\n[DEBUG] Processing company: {company} ({len(listings)} listings)")
                fixedJobs[company] = []

                for (title, jobrightURL, location, workModel, industry, postDate) in listings:
                    print(f"[DEBUG] Processing: {title}")
                    realURL = getApplicationURL(page, jobrightURL)
                    fixedJobs[company].append((title, realURL, location, workModel, industry, postDate))
                    time.sleep(1)

            print(f"\n[DEBUG] Done! Resolved {sum(len(v) for v in fixedJobs.values())} jobs")
            return fixedJobs

        except Exception as e:
            print(f"[DEBUG] Fatal error in skipJobrightPage: {e}")
            return jobs

        finally:
            browser.close()
            print("[DEBUG] Browser closed")
