#!/usr/bin/env python3
"""
Simple Daily Vibe Coding Monitor
Run manually each morning: python monitor.py
Generates: vibe-digest-YYYY-MM-DD.md

No Reddit API key needed - uses public JSON endpoints
Only needs OpenAI API key for analysis
"""

import requests
import json
import time
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
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'VibeCodeMonitor/1.0 (Educational Research)'
        })
    
    def fetch_subreddit_posts(self, subreddit: str, sort: str = 'hot', limit: int = 50) -> List[Dict]:
        """Fetch posts from Reddit using public JSON endpoint (no API key needed)"""
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
    
    def filter_recent_posts(self, posts: List[Dict], hours_back: int = 48) -> List[Dict]:
        """Filter posts from last N hours with basic popularity threshold"""
        cutoff_time = datetime.now().timestamp() - (hours_back * 3600)
        
        filtered = []
        for post in posts:
            # Skip if too old
            if post['created_utc'] < cutoff_time:
                continue
                
            # Skip stickied/pinned posts
            if post.get('stickied', False):
                continue
                
            # Basic engagement threshold (lower since we'll rank anyway)
            if post['score'] >= 3 or post['num_comments'] >= 2:
                filtered.append(post)
        
        return filtered
    
    def analyze_post_relevance(self, post: Dict, subreddit: str) -> Optional[Dict]:
        """Use GPT-4o mini to analyze post relevance to vibe coding"""
        
        # Create analysis prompt with vibe coding context
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
                    'max_tokens': 400,
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
                'score': post['score'],
                'comments': post['num_comments'],
                'created': datetime.fromtimestamp(post['created_utc']).strftime('%Y-%m-%d %H:%M'),
                'author': post.get('author', '[deleted]')
            }
            
            return analysis
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error for post in r/{subreddit}: {e}")
            return None
        except Exception as e:
            print(f"❌ Analysis error for post in r/{subreddit}: {e}")
            return None
    
    def fetch_top_comments(self, permalink: str, limit: int = 3) -> List[Dict]:
        """Fetch top comments for highly relevant posts"""
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
            print(f"❌ Error fetching comments: {e}")
            return []
    
    def run_daily_analysis(self) -> str:
        """Main function to analyze all subreddits and generate report"""
        print("🎨 Starting vibe coding analysis...\n")
        
        all_analyses = []
        total_posts_checked = 0
        
        for subreddit in self.target_subreddits:
            print(f"📡 Analyzing r/{subreddit}...")
            
            # Fetch both hot and new posts for better coverage
            hot_posts = self.fetch_subreddit_posts(subreddit, 'hot', 30)
            new_posts = self.fetch_subreddit_posts(subreddit, 'new', 20)
            
            # Combine and deduplicate
            all_posts = {post['id']: post for post in hot_posts + new_posts}
            recent_posts = self.filter_recent_posts(list(all_posts.values()))
            
            print(f"   Found {len(recent_posts)} recent posts")
            total_posts_checked += len(recent_posts)
            
            for post in recent_posts:
                analysis = self.analyze_post_relevance(post, subreddit)
                
                if analysis and analysis['relevance_score'] >= 5:  # Lower threshold, we'll rank later
                    # Fetch comments for highly relevant posts
                    if analysis['relevance_score'] >= 8:
                        analysis['top_comments'] = self.fetch_top_comments(post['permalink'])
                    
                    all_analyses.append(analysis)
                
                # Rate limiting to be respectful
                time.sleep(0.5)
            
            print(f"   ✅ Found {len([a for a in all_analyses if a['post_data']['subreddit'] == subreddit])} relevant posts")
        
        print(f"\n📊 Total posts analyzed: {total_posts_checked}")
        print(f"📊 Relevant posts found: {len(all_analyses)}")
        
        return self.generate_markdown_report(all_analyses)
    
    def generate_markdown_report(self, analyses: List[Dict]) -> str:
        """Generate a comprehensive markdown report"""
        if not analyses:
            return f"# 🎨 Vibe Coding Digest - {datetime.now().strftime('%B %d, %Y')}\n\nNo relevant discussions found today."
        
        # Sort by relevance score, then engagement
        analyses.sort(key=lambda x: (
            x['relevance_score'], 
            x['post_data']['score'] + x['post_data']['comments']
        ), reverse=True)
        
        # Category mapping
        categories = {
            'app_idea': '💡 App Ideas & Concepts',
            'pain_point': '😤 Pain Points & Frustrations',
            'tool_review': '🛠️ Tool Reviews & Discussions',
            'success_story': '🎉 Success Stories',
            'vibe_coding_discussion': '🌟 Vibe Coding Discussions',
            'show_and_tell': '🚀 Show & Tell Projects',
            'other': '🔍 Other Relevant'
        }
        
        # Start building report
        report = f"# 🎨 Vibe Coding Digest - {datetime.now().strftime('%B %d, %Y')}\n\n"
        report += f"*Found {len(analyses)} relevant discussions about vibe coding and creative app development*\n\n"
        
        # Quick stats
        high_relevance = len([a for a in analyses if a['relevance_score'] >= 8])
        medium_relevance = len([a for a in analyses if 6 <= a['relevance_score'] < 8])
        
        report += f"## 📈 Today's Breakdown\n\n"
        report += f"- 🎯 **{high_relevance}** high-relevance posts (8-10/10)\n"
        report += f"- 🎯 **{medium_relevance}** medium-relevance posts (6-7/10)\n"
        report += f"- 📱 Most active subreddit: **r/{max(set(a['post_data']['subreddit'] for a in analyses), key=lambda x: len([a for a in analyses if a['post_data']['subreddit'] == x]))}**\n\n"
        
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
                report += f"**r/{post['subreddit']}** • {post['score']}↑ • {post['comments']}💬 • {relevance_emoji} {analysis['relevance_score']}/10\n\n"
                report += f"**Summary:** {analysis['summary']}\n\n"
                
                # Add comments for top posts
                if analysis.get('top_comments'):
                    report += f"**💬 Top Comments:**\n"
                    for comment in analysis['top_comments'][:2]:
                        report += f"> *{comment['body']}* - u/{comment['author']} ({comment['score']}↑)\n\n"
                
                report += f"[**👀 Read Full Discussion**]({post['url']})\n\n"
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