import os
import time
import json
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

EMAIL = os.getenv("JOBRIGHT_EMAIL")
PASSWORD = os.getenv("JOBRIGHT_PASSWORD")

# We store the session cookies in a local file so we can reuse them
# across runs and skip the login step when the session is still valid.
SESSION_FILE = "jobright_session.json"


# This opens an invisible chromium browser.
def getBrowser(playwright):
    print("Launching Chromium...")
    return playwright.chromium.launch(headless=True)


# Saves the current browser context cookies to a file.
def saveSession(context):
    cookies = context.cookies()
    with open(SESSION_FILE, "w") as f:
        json.dump(cookies, f)
    print(f"Session saved ({len(cookies)} cookies).")


# Loads cookies from file into the browser context.
def loadSession(context):
    if not os.path.exists(SESSION_FILE):
        return False
    try:
        with open(SESSION_FILE, "r") as f:
            cookies = json.load(f)
        context.add_cookies(cookies)
        print(f"Session loaded ({len(cookies)} cookies).")
        return True
    except Exception as e:
        print(f"Failed to load session: {e}")
        return False


# Checks if we're actually logged in by looking for a sign in button.
def isLoggedIn(page):
    try:
        page.goto("https://jobright.ai/", timeout=10000)
        page.wait_for_load_state("domcontentloaded", timeout=5000)
        signInVisible = page.locator("text=SIGN IN").is_visible()
        return not signInVisible
    except Exception as e:
        print(f"Session check failed: {e}")
        return False


# This automatically navigates to jobright and logs into the pre-made account.
def loginToJobright(page, context, email, password):
    print(f"Navigating to https://jobright.ai/...")
    page.goto("https://jobright.ai/")

    # Waits for and clicks the sign in button to open the login popup.
    print("Waiting for sign in button...")
    page.wait_for_selector("text=SIGN IN", timeout=10000)
    page.click("text=SIGN IN")

    # Waits for the popup email field to appear, then fills in the credentials.
    print("Waiting for email input in popup...")
    page.wait_for_selector("input[placeholder='Email']", timeout=10000)
    page.fill("input[placeholder='Email']", email)
    page.fill("input[placeholder='Password']", password)

    # Clicks the sign in button inside the popup to submit credentials.
    print("Clicking submit...")
    page.click("#sign-in-content button:has-text('SIGN IN')")

    # Waits for the popup to disappear, which confirms login was successful.
    print("Waiting for login modal to close...")
    page.wait_for_selector(".ant-modal-content", state="hidden", timeout=15000)
    print(f"Login successful! Current URL: {page.url}")

    # Saves the session so we can skip login next time.
    saveSession(context)


def getApplicationURL(page, jobURL):
    print(f"\nNavigating to job URL: {jobURL}")
    context = page.context
    page.goto(jobURL, timeout=15000)

    try:
        page.wait_for_load_state("domcontentloaded", timeout=5000)
    except:
        pass

    print(f"Page loaded. Current URL: {page.url}")

    try:
        applyButton = None

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

        try:
            with context.expect_page(timeout=4000) as newPageInfo:
                applyButton.click()

                try:
                    page.wait_for_selector("text=Apply Without Customizing", timeout=2000)
                    print("Resume modal appeared, clicking 'Apply Without Customizing'...")
                    page.click("text=Apply Without Customizing")
                except:
                    pass

            newPage = newPageInfo.value
            newPage.wait_for_load_state("domcontentloaded", timeout=5000)
            realURL = newPage.url
            print(f"New tab opened with URL: {realURL}")
            newPage.close()
            return realURL

        except Exception as e:
            print(f"No new tab detected ({e}), checking for same-tab redirect...")
            time.sleep(1)
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
            # Try loading a cached session first to skip login.
            sessionLoaded = loadSession(context)

            if sessionLoaded and isLoggedIn(page):
                print("Reusing cached session, skipping login.")
            else:
                print("No valid session found, logging in...")
                loginToJobright(page, context, EMAIL, PASSWORD)

            fixedJobs = {}

            for company, listings in jobs.items():
                print(f"\nProcessing company: {company} ({len(listings)} listings)")
                fixedJobs[company] = []

                for (title, jobrightURL, location, workModel, industry, postDate) in listings:
                    print(f"Processing: {title}")
                    realURL = getApplicationURL(page, jobrightURL)
                    fixedJobs[company].append((title, realURL, location, workModel, industry, postDate))

            print(f"\nDone! Resolved {sum(len(v) for v in fixedJobs.values())} jobs")
            return fixedJobs

        except Exception as e:
            print(f"Fatal error in skipJobrightPage: {e}")
            return jobs

        finally:
            browser.close()
            print("Browser closed")
