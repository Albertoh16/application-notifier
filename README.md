# Job Posting Emailer

This is basically a job scraping tool that automatically emails you internship postings from [Jobright] every 6 hour intervals in the day.
---

## How It Works

1. **Scraper** opens a Chromium browser and navigates to the Jobright SWE internship listing page.
2. It captures all jobs posted within 6 hours.
3. Each job is filtered based on your custom keywords in `config.py` by position title, role, qualifications, industry, and excluded words
4. Jobs posted within the last 6 hours that pass your filters are collected and formatted into an email.
5. The email is sent from a dedicated bot Gmail account to your personal email.
6. The whole process runs automatically via GitHub Actions on a schedule.

## "How can I get in on this???"
 
This project uses a shared bot email (`jobnotifier.bot@gmail.com`) to send job notifications. Users create a branch off the main repo to customize their filters, and I'll graciously handle the rest.
 
---
 
## How to Get Added
 
1. **Create a branch** off `main` named after yourself (e.g. `albert`, `user2`).
2. **Edit `bin/config.py`** on your branch to set your personal filters.
3. **Commit and push** your branch.
4. **Contact Me** with your branch name and personal email address.
5. I'll add your environment secret and workflow job.
6. Your personalized job notifications will begin running on the scheduled workflow.
7. Pray to any god that you get a job in our current job market!
 
---

Good luck, I know I need it!
