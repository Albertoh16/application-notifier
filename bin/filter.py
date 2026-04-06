from sentence_transformers import util
import torch

# Model is loaded lazily, only when FilterJobs is first called.
# This means importing filter.py has no cost.
MODEL = None

def getModel():
    global MODEL

    # We'll import our model if it hasn't been imported already.
    if MODEL is None:

        from sentence_transformers import SentenceTransformer   
        print("[Filter] Loading sentence-transformer model...")
        MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        print("[Filter] Model loaded.")

    return MODEL

# This is our threshold in which our model will use to pass our inclusion keywords.
INCLUDE_THRESHOLD = 0.25

# Concatenates job fields into a single string for embedding.
def buildJobText(title: str, qualifications: str, industry: list) -> str:
    industryStr = ", ".join(industry) if industry else ""
    parts = [p for p in [title, qualifications, industryStr] if p and p.strip()]

    return " | ".join(parts)

# Collapses all inclusion filter keywords into one natural language query.
def buildIncludeQuery(filters: dict) -> str | None:
    keys = ["job-titles", "position", "specialization", "qualification", "industry"]
    terms = []

    for key in keys:
        terms.extend(filters.get(key, set()))

    return " ".join(terms) if terms else None

# Returns the first keyword found as a substring of target.
def matchesAny(keywords: set, target: str) -> str | None:
    targetLower = target.lower()

    for keyword in keywords:
        if keyword.lower() in targetLower:
            return keyword
        
    return None

# Checks each exclusion category against its corresponding job field.
def excludeCheck(title: str, qualifications: str, industry: list, filters: dict) -> str | None:
    industryStr = ", ".join(industry) if industry else ""
    qualStr = qualifications or ""

    # We'll get our positions and specializations to check against the job title.
    titleKeywords = (
        filters.get("exclude position", set()) |
        filters.get("exclude specialization", set())
    )

    # We'll now check our exclusion keywords against our job title.
    matched = matchesAny(titleKeywords, title)

    if matched:
        return f"title:'{matched}'"

    # We then check our qualifications against jobs' qualifications field.
    matched = matchesAny(filters.get("exclude qualification", set()), qualStr)

    if matched:
        return f"qualification:'{matched}'"

     # We then check our industries against jobs' industries field.
    matched = matchesAny(filters.get("exclude industry", set()), industryStr)

    if matched:
        return f"industry:'{matched}'"

    return None

# Checks if a job's location contains the user's chosen country.
# Empty country filter means we accept everything.
def countryCheck(location: str, filters: dict) -> bool:
    country = filters.get("country", "")
    if not country:
        return True
    return country.lower() in location.lower()

# Checks if a job's work model matches any of the user's chosen models.
# Empty work-model filter means we accept everything.
def workModelCheck(workModel: str, filters: dict) -> bool:
    allowed = filters.get("work-model", set())
    if not allowed:
        return True
    return workModel.lower() in {m.lower() for m in allowed}

# Uses the ML embeddings for inclusion scoring and uses substring matching for exclusions.
def FilterJobs(filters: dict, resolvedJobs: dict) -> dict:
    if not resolvedJobs:
        return {}

    model = getModel()

    includeQuery = buildIncludeQuery(filters)
    includeEmbedding = model.encode(includeQuery, convert_to_tensor=True) if includeQuery else None

    # (company, title, url, location, workModel, industry, postDate, qualifications)
    flatJobs = []
    jobTexts = []

    for company, listings in resolvedJobs.items():
        for (title, url, location, workModel, industry, postDate, qualifications) in listings:
            flatJobs.append((company, title, url, location, workModel, industry, postDate, qualifications))
            jobTexts.append(buildJobText(title, qualifications, industry))

    if not flatJobs:
        return {}

    print(f"[Filter] Encoding {len(jobTexts)} jobs...")

    jobEmbeddings = model.encode(jobTexts, convert_to_tensor=True, batch_size=64)

    print(f"[Filter] Scoring jobs...")

    userJobs: dict[str, list] = {}

    for i, job in enumerate(flatJobs):
        company, title, url, location, workModel, industry, postDate, qualifications = job
        jobEmb = jobEmbeddings[i]

        # Country filter.
        if not countryCheck(location, filters):
            print(f"[EXCLUDED] '{title}', location '{location}' not in country '{filters.get('country')}'")
            continue

        # Work-model filter.
        if not workModelCheck(workModel, filters):
            print(f"[EXCLUDED] '{title}', work model '{workModel}' not in {filters.get('work-model')}")
            continue

        # Substring exclusion across title, qualifications, and industry.
        excludeMatch = excludeCheck(title, qualifications, industry, filters)

        if excludeMatch:
            print(f"[EXCLUDED] '{title}', matched {excludeMatch}")
            continue

        # ML inclusion check.
        if includeEmbedding is not None:
            score = util.cos_sim(jobEmb, includeEmbedding).item()

            if score < INCLUDE_THRESHOLD:
                print(f"[SKIPPED] '{title}', include score {score:.3f}")
                continue

            print(f"[PASS] '{title}', include score {score:.3f}")

        else:
            print(f"[PASS] '{title}', no include filters")

        if company not in userJobs:
            userJobs[company] = []

        userJobs[company].append((title, url, location, workModel, industry, postDate, qualifications))

    # We return a map of our jobs with the company names as keys.
    return dict(
        sorted(userJobs.items(), key=lambda x: max(j[5] for j in x[1]), reverse=True)
    ) if userJobs else {}