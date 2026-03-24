import os
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

EMAIL = os.getenv("JOBRIGHT_EMAIL")
PASSWORD = os.getenv("JOBRIGHT_PASSWORD")


# This opens an invisible chromium-based browser.
def getBrowser(playwright):
    print("Launching Chromium...")
    return playwright.chromium.launch(headless=True)


# This automatically navigates to jobright and logs into the pre-made account.
def loginToJobright(page, email, password):
    print(f"Navigating to https://jobright.ai/...")
    page.goto("https://jobright.ai/")
    print(f"Current URL after goto: {page.url}")

    # Waits for and clicks the sign in button to open the login popup.
    print("Waiting for sign in button...")
    page.wait_for_selector("text=SIGN IN", timeout=10000)
    print("Clicking SIGN IN button...")
    page.click("text=SIGN IN")

    # Waits for the popup email field to appear, then it fills in the credentials.
    print("Waiting for email input in popup...")
    page.wait_for_selector("input[placeholder='Email']", timeout=10000)
    print("Filling email...")
    page.fill("input[placeholder='Email']", email)

    print("Filling password...")
    page.fill("input[placeholder='Password']", password)

    # Clicks the sign in button inside the popup to submit credentials.
    print("Clicking submit...")
    page.click("#sign-in-content button:has-text('SIGN IN')")

    # Waits for the popup to disappear, which confirms login was successful.
    print("Waiting for login modal to close...")
    page.wait_for_selector(".ant-modal-content", state="hidden", timeout=15000)
    print(f"Login successful! Current URL: {page.url}")
    time.sleep(2)

def getApplicationURL(page, jobURL):
    print(f"\nNavigating to job URL: {jobURL}")
    context = page.context
    page.goto(jobURL, timeout=15000)

    # Waits for the page to fully load, we timeout if that fails to happen.
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except:
        pass

    print(f"Page loaded. Current URL: {page.url}")

    try:
        applyButton = None

        # We try multiple selectors to find the apply button.
        selectors = [
            ".index_applyButton__k3XwL",
            "text=Apply Now",
            "button:has-text('APPLY NOW')",
        ]

        for selector in selectors:
            try:
                btn = page.locator(selector).first
                if btn.is_visible():
                    print(f"Found apply button with selector: '{selector}'")
                    applyButton = btn
                    break
                else:
                    print(f"Selector '{selector}' found but not visible")
            except Exception as e:
                print(f"Selector '{selector}' failed: {e}")
                continue

        if not applyButton:
            print(f"No apply button found on {jobURL}, returning original URL")
            return jobURL

        # Listens for a new tab opening at the moment of the click.
        try:
            with context.expect_page(timeout=8000) as newPageInfo:
                applyButton.click()

                # If a resume popup appeared, we dismiss it to trigger the real link.
                try:
                    page.wait_for_selector("text=Apply Without Customizing", timeout=4000)
                    print("Resume modal appeared, clicking 'Apply Without Customizing'...")
                    page.click("text=Apply Without Customizing")
                except:
                    # No popup means the new tab should already be opening from the click.
                    pass

            newPage = newPageInfo.value
            newPage.wait_for_load_state("load", timeout=10000)
            realURL = newPage.url
            print(f"New tab opened with URL: {realURL}")
            newPage.close()
            return realURL

        except Exception as e:
            # If no new tab opened at all, we check for a redirect within the same tab.
            print(f"No new tab detected ({e}), checking for same-tab redirect...")
            time.sleep(3)
            realURL = page.url

            if realURL != jobURL:
                print(f"Same-tab redirect to: {realURL}")
                page.go_back()
                return realURL

            print(f"No redirect found, returning original Jobright URL")
            return jobURL

    except Exception as e:
        print(f"Exception in getApplicationURL: {e}")
        return jobURL


# This fetches the actual application URL and replaces the jobright URL in the original listing.
def skipJobrightPage(jobs: dict) -> dict:
    print(f"\nskipJobrightPage called with {sum(len(v) for v in jobs.values())} total jobs across {len(jobs)} companies")
    print(f"EMAIL loaded: {'yes' if EMAIL else 'NO - CHECK SECRETS'}")
    print(f"PASSWORD loaded: {'yes' if PASSWORD else 'NO - CHECK SECRETS'}")

    with sync_playwright() as playwright:
        browser = getBrowser(playwright)
        context = browser.new_context()
        page = context.new_page()

        try:
            loginToJobright(page, EMAIL, PASSWORD)

            fixedJobs = {}

            for company, listings in jobs.items():
                print(f"\nProcessing company: {company} ({len(listings)} listings)")
                fixedJobs[company] = []

                for (title, jobrightURL, location, workModel, industry, postDate) in listings:
                    print(f"Processing: {title}")
                    realURL = getApplicationURL(page, jobrightURL)
                    fixedJobs[company].append((title, realURL, location, workModel, industry, postDate))
                    time.sleep(1)

            print(f"\nDone! Resolved {sum(len(v) for v in fixedJobs.values())} jobs")
            return fixedJobs

        except Exception as e:
            print(f"Fatal error in skipJobrightPage: {e}")
            return jobs

        finally:
            browser.close()
            print("Browser closed")
