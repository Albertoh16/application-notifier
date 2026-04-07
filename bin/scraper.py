from playwright.sync_api import sync_playwright
from config import USERS
from emailer import sendEmail
from filter import FilterJobs
from datetime import datetime, timedelta, timezone
import asyncio

from zoneinfo import ZoneInfo
ET = ZoneInfo("America/New_York")

initialTime = datetime.now(tz=timezone.utc)

# Hard-coded to a single user with a fixed 6-hour lookback window.
TARGET_EMAIL = "jobsforalbert16@gmail.com"

if TARGET_EMAIL not in USERS:
    print(f"{TARGET_EMAIL} not found in config, exiting.")
    exit()

activeUsers = {TARGET_EMAIL: USERS[TARGET_EMAIL]}

print(f"Running for {TARGET_EMAIL}")

# Fixed 6-hour lookback — ignores interval/day scheduling.
windowStarts = {
    TARGET_EMAIL: initialTime - timedelta(hours=6)
}

earliestStart = windowStarts[TARGET_EMAIL]

print(f"Scraping window: {earliestStart} -> {initialTime}")

# Uses a single browser to run everything.
with sync_playwright() as p:
    print("Launching Chromium...")
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()

    scrapePage = context.new_page()

    jobs    = []
    seenIds = set()

    def handleResponse(response):
        if "swan/mini-sites/list" in response.url:
            try:
                data = response.json()
                if "result" in data and "jobList" in data["result"]:
                    for job in data["result"]["jobList"]:
                        jobId = job["jobId"]
                        if jobId not in seenIds:
                            seenIds.add(jobId)
                            jobs.append({
                                "title":          job["properties"]["title"],
                                "company":        job["properties"]["company"],
                                "location":       job["properties"]["location"],
                                "workModel":      job["properties"]["workModel"],
                                "applyUrl":       f"https://jobright.ai/jobs/info/{jobId}",
                                "industry":       job["properties"]["industry"],
                                "qualifications": job["properties"]["qualifications"],
                                "postedDate":     job["postedAt"]
                            })

            except Exception as e:
                print(f"Error: {e}")

    scrapePage.on("response", handleResponse)
    scrapePage.goto("https://jobright.ai/minisites-jobs/intern/us/swe")
    scrapePage.wait_for_load_state("domcontentloaded")

    data = scrapePage.evaluate("""() => JSON.parse(document.getElementById('__NEXT_DATA__').textContent)""")

    for job in data["props"]["pageProps"]["initialJobs"]:
        jobId = job["id"]

        if jobId not in seenIds:
            seenIds.add(jobId)
            
            jobs.append({
                "title":          job["title"],
                "company":        job["company"],
                "location":       job["location"],
                "workModel":      job["workModel"],
                "applyUrl":       job["applyUrl"],
                "industry":       job["industry"],
                "qualifications": job["qualifications"],
                "postedDate":     job["postedDate"]
            })

    tableBody = scrapePage.query_selector(".index_bodyViewport__3xQLm")

    STALE_STREAK_LIMIT = 5

    for _ in range(50):
        prevCount = len(seenIds)
        tableBody.evaluate("el => el.scrollTop += 3000")
        scrapePage.wait_for_timeout(600)

        if len(seenIds) == prevCount:
            print(f"No new jobs after scroll, stopping at {len(seenIds)} jobs.")
            break

        recentJobs = sorted(jobs, key=lambda j: j["postedDate"], reverse=True)

        outOfWindow = sum(
            1 for j in recentJobs[:STALE_STREAK_LIMIT]
            if datetime.fromtimestamp(j["postedDate"] / 1000, tz=timezone.utc) < earliestStart
        )

        if outOfWindow >= STALE_STREAK_LIMIT:
            print(f"Last {STALE_STREAK_LIMIT} jobs all outside window, stopping at {len(seenIds)} jobs.")
            break

    scrapePage.close()
    print("Scraping tab closed.")

    allNeededJobs = {}

    for job in jobs:
        if job["company"] not in allNeededJobs:
            allNeededJobs[job["company"]] = []

        allNeededJobs[job["company"]].append((
            job["title"], job["applyUrl"], job["location"],
            job["workModel"], job["industry"], job["postedDate"],
            job["qualifications"]
        ))

    for company in allNeededJobs:
        allNeededJobs[company].sort(key=lambda x: x[5], reverse=True)

    resolvedJobs = {}

    for company, listings in allNeededJobs.items():
        resolvedJobs[company] = []

        for (title, jobrightURL, location, workModel, industry, postDate, qualifications) in listings:
            resolvedJobs[company].append((title, jobrightURL, location, workModel, industry, postDate, qualifications))

    browser.close()
    print("Browser closed.")

async def processUser(email, filters, resolvedJobs, initialTime):
    windowStart = windowStarts[email]

    print(f"\n[{email}] Window: {windowStart} → {initialTime}")

    userResolvedJobs = {
        company: [
            job for job in listings
            if datetime.fromtimestamp(job[5] / 1000, tz=timezone.utc) >= windowStart
        ]
        for company, listings in resolvedJobs.items()
    }

    userResolvedJobs = {k: v for k, v in userResolvedJobs.items() if v}

    userJobs = await asyncio.to_thread(FilterJobs, filters, userResolvedJobs)
    totalJobs = sum(len(v) for v in userJobs.values())

    print(f"[{email}] Sending {totalJobs} jobs.")

    await asyncio.to_thread(sendEmail, userJobs, initialTime, email)

async def processAllUsers(resolvedJobs, initialTime):
    tasks = [
        processUser(email, filters, resolvedJobs, initialTime)
        for email, filters in activeUsers.items()
    ]
    await asyncio.gather(*tasks)

asyncio.run(processAllUsers(resolvedJobs, initialTime))
