from jobspy import scrape_jobs
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

# Sites to scrape from.
JOBSPY_SITES = ["indeed", "linkedin", "zip_recruiter", "google", "glassdoor"]

# Results requested per site per query.
RESULTS_PER_SITE = 200

# Maps job_type values to workModel format.
WORK_MODEL_MAP = {
    "remote":    "Remote",
    "hybrid":    "Hybrid",
    "onsite":    "On-site",
    "on-site":   "On-site",
    "on_site":   "On-site",
    "fulltime":  "On-site",
}

# Indeed requires a country code string. So we map the lowercase country names to codes.
# Unsupported countries are skipped.
INDEED_COUNTRY_MAP = {
    "united states": "USA", "united kingdom": "UK", "canada": "Canada",
    "australia": "Australia", "germany": "Germany", "france": "France",
    "india": "India", "netherlands": "Netherlands", "singapore": "Singapore",
    "new zealand": "New Zealand", "ireland": "Ireland", "spain": "Spain",
    "italy": "Italy", "brazil": "Brazil", "mexico": "Mexico",
    "south africa": "South Africa", "austria": "Austria", "belgium": "Belgium",
    "switzerland": "Switzerland", "sweden": "Sweden", "norway": "Norway",
    "denmark": "Denmark", "finland": "Finland", "poland": "Poland",
    "portugal": "Portugal", "argentina": "Argentina", "chile": "Chile",
    "colombia": "Colombia", "peru": "Peru", "indonesia": "Indonesia",
    "japan": "Japan", "south korea": "South Korea", "malaysia": "Malaysia",
    "philippines": "Philippines", "thailand": "Thailand", "vietnam": "Vietnam",
    "pakistan": "Pakistan", "nigeria": "Nigeria", "kenya": "Kenya",
    "egypt": "Egypt",
}

def normalizeWorkModel(jobType) -> str:
    if not jobType:
        return "On-site"
    
    return WORK_MODEL_MAP.get(str(jobType).lower().replace(" ", "_"), "On-site")

def normalizeLocation(city, state, country) -> str:
    parts = [p for p in [city, state, country] if p and str(p) != "nan" and str(p).strip()]

    return ", ".join(str(p) for p in parts) if parts else "Unknown"

def normalizeDate(datePosted) -> int:
    if datePosted is None or (isinstance(datePosted, float) and pd.isna(datePosted)):
        return int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    
    if isinstance(datePosted, datetime):
        if datePosted.tzinfo is None:
            datePosted = datePosted.replace(tzinfo=timezone.utc)

        return int(datePosted.timestamp() * 1000)
    
    try:
        from datetime import date

        if isinstance(datePosted, date):
            dt = datetime(datePosted.year, datePosted.month, datePosted.day, tzinfo=timezone.utc)
            
            return int(dt.timestamp() * 1000)
        
    except Exception:
        pass

    return int(datetime.now(tz=timezone.utc).timestamp() * 1000)

def normalizeRows(df: pd.DataFrame, earliestStart: datetime, seen: set) -> list:
    results = []

    for _, row in df.iterrows():
        try:
            title   = str(row.get("title")   or "").strip()
            company = str(row.get("company") or "").strip()

            if not title or not company:
                continue

            dedupKey = (company.lower(), title.lower())

            if dedupKey in seen:
                continue

            seen.add(dedupKey)
            postDate = normalizeDate(row.get("date_posted"))

            if datetime.fromtimestamp(postDate / 1000, tz=timezone.utc) < earliestStart:
                continue

            url = str(row.get("job_url_direct") or row.get("job_url") or "").strip()

            if not url:
                continue

            location = normalizeLocation(row.get("city"), row.get("state"), row.get("country"))
            workModel = normalizeWorkModel(row.get("job_type"))
            description = str(row.get("description") or "").strip()
            qualifications = description[:500] if description else ""
            results.append((company, title, url, location, workModel, [], postDate, qualifications))
       
        except Exception as e:
            print(f"[JobSpy] Row error: {e}")

    return results

def runSingleQuery(country: str, jobTitle: str, earliestStart: datetime) -> list:
    indeedCountry = INDEED_COUNTRY_MAP.get(country.lower())
    sites = JOBSPY_SITES if indeedCountry else [s for s in JOBSPY_SITES if s != "indeed"]

    if not sites:
        print(f"[JobSpy] No supported sites for '{country}', skipping.")
        return []

    print(f"[JobSpy] Querying: '{jobTitle}' in '{country}' via {sites}")

    try:
        kwargs = dict(
            site_name=sites,
            search_term=jobTitle,
            results_wanted=RESULTS_PER_SITE,
            hours_old=26,
            linkedin_fetch_description=True,
        )

        if indeedCountry:
            kwargs["country_indeed"] = indeedCountry

        df = scrape_jobs(**kwargs)

    except Exception as e:
        print(f"[JobSpy] Query failed ('{jobTitle}' / '{country}'): {e}")
        return []

    if df is None or df.empty:
        print(f"[JobSpy] No results for '{jobTitle}' in '{country}'.")
        return []

    print(f"[JobSpy] '{jobTitle}' / '{country}': {len(df)} raw results")

    # Each query gets its own seen set, then it cross-queries to dedup fetchJobSpyJobs.
    return normalizeRows(df, earliestStart, set())

def buildQueryPairs(activeUsers: dict) -> list:
    pairs: set = set()

    for filters in activeUsers.values():
        country   = filters.get("country", "").strip().lower()
        jobTitles = filters.get("job-titles", set())

        if not country:
            continue

        if jobTitles:
            for title in jobTitles:
                pairs.add((country, title.strip()))

        else:
            print(f"[JobSpy] No job titles for a user in '{country}', skipping that user.")
    
    return list(pairs)

# Takes the unique (country, jobTitle) pairs across all active users, runs one
# JobSpy query per pair concurrently, and then merges and deduplicates into a
# single company-keyed dict in the standard tuple format.
def fetchJobSpyJobs(activeUsers: dict, earliestStart: datetime) -> dict:
    pairs = buildQueryPairs(activeUsers)

    if not pairs:
        print("[JobSpy] No (country, jobTitle) pairs found, skipping.")
        return {}

    print(f"[JobSpy] Running {len(pairs)} queries: {pairs}")

    allTuples: list = []

    with ThreadPoolExecutor(max_workers=min(len(pairs), 6)) as executor:
        futures = {
            executor.submit(runSingleQuery, country, jobTitle, earliestStart): (country, jobTitle)
            for country, jobTitle in pairs
        }

        for future in as_completed(futures):
            country, jobTitle = futures[future]
            
            try:
                tuples = future.result()
                allTuples.extend(tuples)
                print(f"[JobSpy] '{jobTitle}' / '{country}': {len(tuples)} normalized jobs")
            
            except Exception as e:
                print(f"[JobSpy] Future error ('{jobTitle}', '{country}'): {e}")

    # Performs cross-query deduplication then restructures it into a company keyed map.
    jobs: dict = {}
    seen: set  = set()

    for (company, title, url, location, workModel, industry, postDate, qualifications) in allTuples:
        key = (company.lower(), title.lower())

        if key in seen:
            continue

        seen.add(key)

        if company not in jobs:
            jobs[company] = []

        jobs[company].append((title, url, location, workModel, industry, postDate, qualifications))

    for company in jobs:
        jobs[company].sort(key=lambda x: x[5], reverse=True)

    total = sum(len(v) for v in jobs.values())
    print(f"[JobSpy] Total after dedup: {total} jobs across {len(jobs)} companies.")

    return jobs