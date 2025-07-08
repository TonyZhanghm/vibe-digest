# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Vibe Coding Daily Digest** project that monitors Reddit and Hacker News for discussions about "vibe coding" - intuitive, creative, visual app development. The project generates daily markdown reports analyzing relevant posts and discussions.

## Core Architecture

- **Single Python Script**: `monitor.py` contains all functionality
- **Data Sources**: Reddit (public JSON endpoints) and Hacker News (free Firebase API)
- **Analysis Engine**: OpenAI GPT-4o mini for content relevance scoring
- **Output**: Daily markdown reports in `digests/` directory

## Key Components

### VibeCodeMonitor Class
- `fetch_reddit_posts()`: Retrieves posts from target subreddits
- `fetch_hn_stories()`: Gets stories from HN (ask, show, top categories)
- `analyze_reddit_post()` / `analyze_hn_story()`: Uses GPT-4o mini to score relevance (1-10)
- `generate_markdown_report()`: Creates formatted daily digest

### Target Communities
- **Reddit**: r/nocode, r/SideProject, r/indiehackers, r/AppIdeas, r/creativecoding, r/vibecoding, r/ClaudeAI
- **HN**: Ask HN, Show HN, and top stories with relevant keywords

## Running the Project

```bash
# Set OpenAI API key
export OPENAI_API_KEY="your-key-here"

# Run daily analysis
python monitor.py
```

## Dependencies

Install required packages:
```bash
pip install requests python-dotenv
```

## Environment Variables

Required in `.env` file:
- `OPENAI_API_KEY`: OpenAI API key for GPT-4o mini analysis

## Output Format

Daily reports are saved as `digests/vibe-digest-YYYY-MM-DD.md` with:
- Categorized posts by relevance score
- Top comments for highly relevant posts
- Engagement metrics (upvotes, comments)
- Direct links to discussions

## Rate Limiting

- Reddit: 0.5 second delay between requests
- HN: 0.1 second delay between API calls
- OpenAI: 0.5 second delay between analysis calls

## Filtering Criteria

- **Reddit**: Posts from last 48 hours with score ≥3 or comments ≥2
- **HN**: Stories from last 48 hours with vibe coding keywords
- **Relevance**: Only scores 6+ are included in final report