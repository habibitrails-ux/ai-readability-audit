# AI Readability Audit Web Application

An automated web diagnostic tool built with Flask and Vercel that evaluates websites for AI search engine optimization (crawlers like GPTBot, Perplexity, and Google AI Overviews).

## Features

- **Bot Accessibility & Sitemap Check:** Scans `robots.txt` and `sitemap.xml` for crawler blocks.
- **Structured Data & Semantic HTML Parsing:** Detects schema JSON-LD markup and semantic containers.
- **Automated Fix Recommendations:** Generates copy-pasteable JSON-LD and `robots.txt` snippets for low scores.
- **User Authentication & Credit System:**
  - New user sign-up comes with **2 free credits**.
  - 1 credit deducted per site audit.
  - Interactive pricing modal pops up when credits reach 0.

## Tech Stack

- **Backend:** Python / Flask
- **Frontend:** HTML5, JavaScript (Fetch API), Tailwind CSS
- **Deployment:** Vercel Serverless (`@vercel/python`)
-
