#!/usr/bin/env python3
"""
Clean Vibe Coding Monitor - Reddit + Hacker News
Run manually each morning: python monitor.py
Generates: vibe-digest-YYYY-MM-DD.md

No Reddit API key needed - uses public JSON endpoints
HN uses free Firebase API
Only needs OpenAI API key for analysis
"""

import requests
import json
import time
import re
from datetime import datetime, timedelta
import os
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

class VibeCodeMonitor:
    def __init__(self, openai_api_key: str):
        self.openai_api_key = openai_api_key
        self.target_subreddits = [
            'nocode', 'SideProject', 'indiehackers', 'AppIdeas', 
            'creativecoding', 'vibecoding', 'ClaudeAI'
        ]
        
        # Setup HTTP session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'VibeCodeMonitor/1.0 (Educational Research)'
        })
        
        # HN API base URL (free, no key needed)
        self.hn_api_base = "https://hacker-news.firebaseio.com/v0"
    
    # === REDDIT FUNCTIONS ===
    
    def fetch_reddit_posts(self, subreddit: str, sort: str = 'hot', limit: int = 50) -> List[Dict]:
        """Fetch posts from Reddit using public JSON endpoint"""
        try:
            url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit={limit}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            posts = []
            
            for item in data['data']['children']:
                post = item['data']
                posts.append(post)
            
            return posts
            
        except Exception as e:
            print(f"❌ Error fetching r/{subreddit}: {e}")
            return []
    
    def filter_recent_reddit_posts(self, posts: List[Dict], hours_back: int = 48) -> List[Dict]:
        """Filter Reddit posts from last N hours with basic popularity threshold"""
        cutoff_time = datetime.now().timestamp() - (hours_back * 3600)
        
        filtered = []
        for post in posts:
            # Skip if too old
            if post['created_utc'] < cutoff_time:
                continue
                
            # Skip stickied/pinned posts
            if post.get('stickied', False):
                continue
                
            # Basic engagement threshold
            if post['score'] >= 3 or post['num_comments'] >= 2:
                filtered.append(post)
        
        return filtered
    
    def fetch_reddit_comments(self, permalink: str, limit: int = 3) -> List[Dict]:
        """Fetch top comments for Reddit posts"""
        try:
            url = f"https://www.reddit.com{permalink}.json?limit=1"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if len(data) < 2:
                return []
                
            comments_data = data[1]['data']['children']
            comments = []
            
            for comment_item in comments_data[:limit]:
                comment = comment_item['data']
                if comment.get('body') and comment['body'] != '[deleted]':
                    comments.append({
                        'body': comment['body'][:250] + ('...' if len(comment['body']) > 250 else ''),
                        'score': comment['score'],
                        'author': comment.get('author', '[deleted]')
                    })
            
            return comments
            
        except Exception as e:
            print(f"❌ Error fetching Reddit comments: {e}")
            return []
    
    # === HACKER NEWS FUNCTIONS ===
    
    def fetch_hn_stories(self, story_type: str = 'top', limit: int = 100) -> List[Dict]:
        """Fetch HN stories using free API"""
        try:
            # Get story IDs
            if story_type == 'ask':
                url = f"{self.hn_api_base}/askstories.json"
            elif story_type == 'show':
                url = f"{self.hn_api_base}/showstories.json"
            elif story_type == 'new':
                url = f"{self.hn_api_base}/newstories.json"
            else:  # top
                url = f"{self.hn_api_base}/topstories.json"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            story_ids = response.json()[:limit]
            
            # Get story details
            stories = []
            for story_id in story_ids:
                try:
                    story_url = f"{self.hn_api_base}/item/{story_id}.json"
                    story_response = self.session.get(story_url, timeout=5)
                    story_response.raise_for_status()
                    story = story_response.json()
                    
                    if story and story.get('type') == 'story':
                        stories.append(story)
                    
                    # Rate limiting for HN API
                    time.sleep(0.1)
                    
                except Exception as e:
                    print(f"Error fetching HN story {story_id}: {e}")
                    continue
            
            return stories
            
        except Exception as e:
            print(f"❌ Error fetching HN {story_type} stories: {e}")
            return []
    
    def filter_hn_stories(self, stories: List[Dict], hours_back: int = 48) -> List[Dict]:
        """Filter HN stories for relevance and recency"""
        cutoff_time = datetime.now().timestamp() - (hours_back * 3600)
        
        # Keywords that indicate vibe coding relevance
        vibe_keywords = [
            'no-code', 'nocode', 'low-code', 'visual', 'drag', 'drop',
            'mobile app', 'app builder', 'prototype', 'figma', 'design tool',
            'creative coding', 'bubble', 'webflow', 'glide', 'adalo',
            'ui builder', 'app development', 'rapid prototype', 'tiktok',
            'social app', 'mini app', 'quick app', 'simple app'
        ]
        
        filtered = []
        for story in stories:
            # Skip if too old
            if story.get('time', 0) < cutoff_time:
                continue
            
            # Skip if deleted or no title
            if not story.get('title'):
                continue
                
            # Check for relevant keywords in title and text
            title = story.get('title', '').lower()
            text = story.get('text', '').lower()
            combined_text = f"{title} {text}"
            
            # Always include Ask HN and Show HN posts with keywords
            if (title.startswith('ask hn:') or title.startswith('show hn:')) and \
               any(keyword in combined_text for keyword in vibe_keywords):
                filtered.append(story)
            # Include other posts only if highly relevant
            elif story.get('score', 0) > 10 and \
                 any(keyword in combined_text for keyword in vibe_keywords):
                filtered.append(story)
        
        return filtered
    
    def fetch_hn_comments(self, story: Dict, limit: int = 3) -> List[Dict]:
        """Fetch top comments from an HN story"""
        try:
            comment_ids = story.get('kids', [])[:limit]
            comments = []
            
            for comment_id in comment_ids:
                try:
                    comment_url = f"{self.hn_api_base}/item/{comment_id}.json"
                    response = self.session.get(comment_url, timeout=5)
                    response.raise_for_status()
                    comment = response.json()
                    
                    if comment and comment.get('text'):
                        # Remove HTML tags from comment text
                        clean_text = re.sub('<[^<]+?>', '', comment['text'])
                        comments.append({
                            'text': clean_text[:300] + ('...' if len(clean_text) > 300 else ''),
                            'score': comment.get('score', 0),
                            'by': comment.get('by', 'anonymous')
                        })
                    
                    time.sleep(0.1)  # Rate limiting
                    
                except Exception as e:
                    print(f"Error fetching HN comment {comment_id}: {e}")
                    continue
            
            return comments
            
        except Exception as e:
            print(f"❌ Error fetching HN comments: {e}")
            return []
    
    # === ANALYSIS FUNCTIONS ===
    
    def analyze_reddit_post(self, post: Dict, subreddit: str) -> Optional[Dict]:
        """Use GPT-4o mini to analyze Reddit post relevance to vibe coding"""
        
        prompt = f"""You are analyzing Reddit posts for "vibe coding" - the hot new buzzword for intuitive, creative, visual app development. 

Analyze this post for Crayon, a mobile-first platform where anyone creates mini-apps without coding. Think TikTok for apps: users express ideas through simple, personal, social experiences. Vibe coding is all about making app creation feel natural, creative, and immediate.

Pay special attention to:
- "What are you working on today/this week" posts with interesting responses
- Show and tell posts about projects 
- Pain points with existing tools
- App ideas people want to build
- Creative coding experiments

Subreddit: r/{subreddit}
Title: {post['title']}
Content: {post.get('selftext', '')[:800]}
Engagement: {post['score']} upvotes, {post['num_comments']} comments

Respond with JSON only:
{{
  "relevance_score": 1-10,
  "category": "app_idea|pain_point|tool_review|success_story|vibe_coding_discussion|show_and_tell|other",
  "summary": "2-sentence summary focusing on what's interesting about this post"
}}

Score 8-10: Perfect vibe coding content (mobile app ideas, no-code frustrations, creative coding, good "what are you working on" responses)
Score 6-7: Somewhat relevant (general app development, design tools)
Score 1-5: Not relevant

Respond ONLY with the JSON object."""

        try:
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {self.openai_api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'gpt-4o-mini',
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': 300,
                    'temperature': 0.2
                },
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Parse the JSON response
            analysis_text = result['choices'][0]['message']['content'].strip()
            analysis = json.loads(analysis_text)
            
            # Add post metadata
            analysis['post_data'] = {
                'title': post['title'],
                'url': f"https://reddit.com{post['permalink']}",
                'subreddit': subreddit,
                'source': 'reddit',
                'score': post['score'],
                'comments': post['num_comments'],
                'created': datetime.fromtimestamp(post['created_utc']).strftime('%Y-%m-%d %H:%M'),
                'author': post.get('author', '[deleted]')
            }
            
            return analysis
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error for Reddit post in r/{subreddit}: {e}")
            return None
        except Exception as e:
            print(f"❌ Analysis error for Reddit post in r/{subreddit}: {e}")
            return None
    
    def analyze_hn_story(self, story: Dict) -> Optional[Dict]:
        """Analyze HN story relevance to vibe coding"""
        
        title = story.get('title', '')
        text = story.get('text', '')
        url = story.get('url', '')
        
        # Determine story type
        story_type = 'regular'
        if title.lower().startswith('ask hn:'):
            story_type = 'ask_hn'
        elif title.lower().startswith('show hn:'):
            story_type = 'show_hn'
        
        prompt = f"""You are analyzing Hacker News posts for "vibe coding" - the hot new buzzword for intuitive, creative, visual app development.

Analyze this HN post for Crayon, a mobile-first platform where anyone creates mini-apps without coding. Think TikTok for apps: users express ideas through simple, personal, social experiences.

Pay special attention to:
- Ask HN posts seeking app development advice
- Show HN posts demonstrating creative tools
- Posts about no-code/low-code platforms
- Mobile app development discussions
- Design tool conversations

Story Type: {story_type}
Title: {title}
Content: {text[:800]}
URL: {url}
Score: {story.get('score', 0)} points, {story.get('descendants', 0)} comments

Respond with JSON only:
{{
  "relevance_score": 1-10,
  "category": "ask_hn|show_hn|tool_discussion|mobile_dev|design_tools|other",
  "summary": "2-sentence summary focusing on what makes this interesting for vibe coding"
}}

Score 8-10: Perfect vibe coding content (Ask HN about app tools, Show HN creative projects, no-code discussions)
Score 6-7: Somewhat relevant (general app development, design)
Score 1-5: Not relevant

Respond ONLY with the JSON object."""

        try:
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {self.openai_api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'gpt-4o-mini',
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': 300,
                    'temperature': 0.2
                },
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            analysis_text = result['choices'][0]['message']['content'].strip()
            analysis = json.loads(analysis_text)
            
            # Add HN story metadata
            analysis['post_data'] = {
                'title': title,
                'url': f"https://news.ycombinator.com/item?id={story['id']}",
                'external_url': url,
                'source': 'hackernews',
                'score': story.get('score', 0),
                'comments': story.get('descendants', 0),
                'created': datetime.fromtimestamp(story.get('time', 0)).strftime('%Y-%m-%d %H:%M'),
                'author': story.get('by', 'anonymous'),
                'story_type': story_type
            }
            
            return analysis
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error for HN story: {e}")
            return None
        except Exception as e:
            print(f"❌ Analysis error for HN story: {e}")
            return None
    
    # === MAIN ANALYSIS FUNCTION ===
    
    def run_daily_analysis(self) -> str:
        """Main function to analyze Reddit and HN content"""
        print("🎨 Starting vibe coding analysis...\n")
        
        all_analyses = []
        total_posts_checked = 0
        
        # === REDDIT ANALYSIS ===
        print("📡 Analyzing Reddit...")
        for subreddit in self.target_subreddits:
            print(f"   📊 r/{subreddit}...")
            
            # Fetch both hot and new posts for better coverage
            hot_posts = self.fetch_reddit_posts(subreddit, 'hot', 30)
            new_posts = self.fetch_reddit_posts(subreddit, 'new', 20)
            
            # Combine and deduplicate
            all_posts = {post['id']: post for post in hot_posts + new_posts}
            recent_posts = self.filter_recent_reddit_posts(list(all_posts.values()))
            
            print(f"      Found {len(recent_posts)} recent posts")
            total_posts_checked += len(recent_posts)
            
            for post in recent_posts:
                analysis = self.analyze_reddit_post(post, subreddit)
                
                if analysis and analysis['relevance_score'] >= 6:  # Only 6+ relevance
                    # Fetch comments for highly relevant posts
                    if analysis['relevance_score'] >= 8:
                        analysis['top_comments'] = self.fetch_reddit_comments(post['permalink'])
                    
                    all_analyses.append(analysis)
                
                # Rate limiting
                time.sleep(0.5)
        
        # === HACKER NEWS ANALYSIS ===
        print("\n🧡 Analyzing Hacker News...")
        
        # Fetch different types of HN stories
        hn_story_types = [('ask', 50), ('show', 50), ('top', 100)]
        
        for story_type, limit in hn_story_types:
            print(f"   📊 HN {story_type} stories...")
            stories = self.fetch_hn_stories(story_type, limit)
            filtered_stories = self.filter_hn_stories(stories)
            
            print(f"      Found {len(filtered_stories)} relevant stories")
            total_posts_checked += len(filtered_stories)
            
            for story in filtered_stories:
                analysis = self.analyze_hn_story(story)
                
                if analysis and analysis['relevance_score'] >= 6:  # Only 6+ relevance
                    # Fetch comments for highly relevant HN stories
                    if analysis['relevance_score'] >= 8:
                        analysis['top_comments'] = self.fetch_hn_comments(story)
                    
                    all_analyses.append(analysis)
                
                # Rate limiting
                time.sleep(0.5)
        
        print(f"\n📊 Total posts analyzed: {total_posts_checked}")
        print(f"📊 Relevant posts found: {len(all_analyses)}")
        
        return self.generate_markdown_report(all_analyses)
    
    # === REPORT GENERATION ===
    
    def generate_markdown_report(self, analyses: List[Dict]) -> str:
        """Generate a comprehensive markdown report"""
        if not analyses:
            return f"# 🎨 Vibe Coding Digest - {datetime.now().strftime('%B %d, %Y')}\n\nNo relevant discussions found today."
        
        # Sort by relevance score, then engagement
        analyses.sort(key=lambda x: (
            x['relevance_score'], 
            x['post_data']['score'] + x['post_data']['comments']
        ), reverse=True)
        
        # Category mapping (updated for HN content)
        categories = {
            'app_idea': '💡 App Ideas & Concepts',
            'pain_point': '😤 Pain Points & Frustrations',
            'tool_review': '🛠️ Tool Reviews & Discussions',
            'success_story': '🎉 Success Stories',
            'vibe_coding_discussion': '🌟 Vibe Coding Discussions',
            'show_and_tell': '🚀 Show & Tell Projects',
            'ask_hn': '❓ Ask HN Questions',
            'show_hn': '📦 Show HN Projects',
            'tool_discussion': '⚙️ Tool Discussions',
            'mobile_dev': '📱 Mobile Development',
            'design_tools': '🎨 Design Tools',
            'other': '🔍 Other Relevant'
        }
        
        # Start building report
        report = f"# 🎨 Vibe Coding Digest - {datetime.now().strftime('%B %d, %Y')}\n\n"
        report += f"*Found {len(analyses)} relevant discussions about vibe coding and creative app development*\n\n"
        
        # Quick stats
        high_relevance = len([a for a in analyses if a['relevance_score'] >= 8])
        medium_relevance = len([a for a in analyses if 6 <= a['relevance_score'] < 8])
        reddit_posts = len([a for a in analyses if a['post_data'].get('source') == 'reddit'])
        hn_posts = len([a for a in analyses if a['post_data'].get('source') == 'hackernews'])
        
        report += f"## 📈 Today's Breakdown\n\n"
        report += f"- 🎯 **{high_relevance}** high-relevance posts (8-10/10)\n"
        report += f"- 🎯 **{medium_relevance}** medium-relevance posts (6-7/10)\n"
        report += f"- 📱 **{reddit_posts}** Reddit posts • **{hn_posts}** Hacker News posts\n\n"
        
        # Group by category
        for category_key, category_name in categories.items():
            category_posts = [a for a in analyses if a['category'] == category_key]
            
            if not category_posts:
                continue
            
            report += f"## {category_name}\n\n"
            
            for analysis in category_posts:
                post = analysis['post_data']
                
                # Relevance emoji
                if analysis['relevance_score'] >= 9:
                    relevance_emoji = "🎯🎯🎯"
                elif analysis['relevance_score'] >= 7:
                    relevance_emoji = "🎯🎯"
                else:
                    relevance_emoji = "🎯"
                
                report += f"### {post['title']}\n\n"
                
                # Different formatting for Reddit vs HN
                if post.get('source') == 'hackernews':
                    # Hacker News post
                    hn_type = post.get('story_type', 'regular')
                    report += f"**Hacker News** ({hn_type}) • {post['score']}↑ • {post['comments']}💬 • {relevance_emoji} {analysis['relevance_score']}/10\n\n"
                else:
                    # Reddit post
                    report += f"**r/{post.get('subreddit', 'unknown')}** • {post['score']}↑ • {post['comments']}💬 • {relevance_emoji} {analysis['relevance_score']}/10\n\n"
                
                report += f"**Summary:** {analysis['summary']}\n\n"
                
                # Add comments for top posts (different format for HN vs Reddit)
                if analysis.get('top_comments'):
                    report += f"**💬 Top Comments:**\n"
                    for comment in analysis['top_comments'][:2]:
                        if post.get('source') == 'hackernews':
                            # HN comments have 'text' and 'by' fields
                            report += f"> *{comment.get('text', '')}* - {comment.get('by', 'anonymous')} ({comment.get('score', 0)}↑)\n\n"
                        else:
                            # Reddit comments have 'body' and 'author' fields
                            report += f"> *{comment.get('body', '')}* - u/{comment.get('author', 'anonymous')} ({comment.get('score', 0)}↑)\n\n"
                
                # Link handling - HN posts might have external URLs
                main_link = post['url']
                if post.get('source') == 'hackernews' and post.get('external_url'):
                    report += f"[**👀 Read Discussion**]({main_link}) • [**🔗 External Link**]({post['external_url']})\n\n"
                else:
                    report += f"[**👀 Read Full Discussion**]({main_link})\n\n"
                
                report += "---\n\n"
        
        # Footer with stats
        report += f"*Generated on {datetime.now().strftime('%Y-%m-%d at %H:%M')} • Keep vibing! 🎨*"
        
        return report
    
    def save_report(self, content: str) -> str:
        """Save report to markdown file"""
        filename = f"digests/vibe-digest-{datetime.now().strftime('%Y-%m-%d')}.md"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"\n✅ Report saved to: {filename}")
        return filename

def main():
    """Main execution function"""
    # Check for OpenAI API key
    openai_api_key = os.getenv('OPENAI_API_KEY')
    
    if not openai_api_key:
        print("❌ Please set OPENAI_API_KEY environment variable")
        print("   Example: export OPENAI_API_KEY='your-key-here'")
        return
    
    try:
        print("🚀 Starting Vibe Coding Monitor...")
        print("💡 Using Reddit public JSON endpoints (no Reddit API key needed)")
        print("🧡 Using HN free API (no HN API key needed)")
        print("🤖 Using GPT-4o mini for analysis\n")
        
        monitor = VibeCodeMonitor(openai_api_key)
        report_content = monitor.run_daily_analysis()
        filename = monitor.save_report(report_content)
        
        print(f"\n🎉 Analysis complete!")
        print(f"📄 Your vibe coding digest is ready: {filename}")
        print("☕ Grab some coffee and dive into today's insights!")
        
    except KeyboardInterrupt:
        print("\n👋 Analysis interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")

if __name__ == "__main__":
    main()