"""
Chapter Writer Agent for Multi-AI Book Writing System

This script implements an AI agent that generates mathematical content for a book chapter,
following the Rudin/Atiyah Macdonald academic style, and commits it to GitHub.

The agent:
1. Receives a chapter outline or specification
2. Generates appropriate mathematical content
3. Formats it in LaTeX with proper structure
4. Commits the content to a GitHub branch
5. Creates a pull request for review

Usage:
    python chapter_writer_agent.py --chapter 1 --title "Introduction to Category Theory" --outline "outline.md"
"""

import os
import argparse
import logging
import sys
import json
import anthropic
from datetime import datetime
from github_agent import GitHubAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("chapter_writer.log"), logging.StreamHandler()]
)
logger = logging.getLogger("chapter_writer")

class ChapterWriterAgent:
    """Agent for generating mathematical book chapters"""
    
    def __init__(self, repo_owner, repo_name, config_path="config.json"):
        """
        Initialize the chapter writer agent
        
        Args:
            repo_owner (str): Owner of the GitHub repository
            repo_name (str): Name of the GitHub repository
            config_path (str): Path to configuration file
        """
        # Load configuration
        self.load_config(config_path)
        
        # Initialize GitHub agent
        self.github = GitHubAgent(
            repo_owner=repo_owner,
            repo_name=repo_name,
            agent_name=self.config.get("agent_name", "ChapterWriterAgent")
        )
        
        # Initialize Claude client
        self.client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        
        logger.info(f"Initialized ChapterWriterAgent for {repo_owner}/{repo_name}")
    
    def load_config(self, config_path):
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
            logger.info(f"Loaded configuration from {config_path}")
        except FileNotFoundError:
            logger.warning(f"Configuration file {config_path} not found. Using defaults.")
            self.config = {
                "agent_name": "ChapterWriterAgent",
                "model": "claude-3-7-sonnet-20250219",
                "style_guide": "math_style_guide.md",
                "template_path": "templates/chapter_template.tex"
            }
    
    def _get_chapter_template(self):
        """Get the chapter template from the repository or local file"""
        template_path = self.config.get("template_path", "templates/chapter_template.tex")
        
        # Try to get from GitHub first
        content = self.github.get_file_content(template_path)
        if content:
            return content
        
        # If not found in repo, try local file
        try:
            with open(template_path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"Template file {template_path} not found. Using default template.")
            return r"""
\chapter{$CHAPTER_TITLE}

% Chapter Introduction
$CHAPTER_INTRODUCTION

% Main Sections
$CHAPTER_SECTIONS

% Chapter Exercises
\section{Exercises}
$CHAPTER_EXERCISES
"""
    
    def _get_style_guide(self):
        """Get the writing style guide"""
        style_path = self.config.get("style_guide", "math_style_guide.md")
        
        # Try to get from GitHub first
        content = self.github.get_file_content(style_path)
        if content:
            return content
        
        # If not found, return default style description
        return """
# Mathematical Writing Style Guide (Rudin/Atiyah Macdonald Academic Style)

## Core Principles
- Balance brevity with pedagogical clarity
- Present definitions precisely, theorems rigorously
- Provide intuition for complex concepts
- Include carefully chosen examples that illustrate key points
- Use consistent notation throughout

## Structure
- Begin with motivating examples or context
- Present definitions before theorems
- Group related concepts together
- End sections with exercises that build understanding

## Language
- Prefer active voice for clarity
- Use first-person plural ("we") rather than second-person
- Maintain formal but accessible tone
- Define terms before using them
- Keep sentences direct and concise

## Mathematical Presentation
- State theorems clearly with all necessary conditions
- Provide complete, rigorous proofs
- Highlight key steps in proofs
- Use examples to illustrate abstract concepts
- Include diagrams where helpful
"""
    
    def generate_chapter_content(self, chapter_number, chapter_title, outline):
        """
        Generate chapter content using Claude
        
        Args:
            chapter_number (int): Chapter number
            chapter_title (str): Chapter title
            outline (str): Chapter outline or detailed description
            
        Returns:
            str: LaTeX content for the chapter
        """
        # Get template and style guide
        template = self._get_chapter_template()
        style_guide = self._get_style_guide()
        
        # Construct prompt for Claude
        prompt = f"""
You are writing Chapter {chapter_number}: {chapter_title} for a mathematics textbook.

# Chapter Outline/Specification:
{outline}

# Writing Style:
{style_guide}

# Task:
Write this chapter in LaTeX format, following the outline provided and adhering to the writing style guide.
The chapter should be comprehensive and mathematically rigorous, but also pedagogically sound.

Important LaTeX guidelines:
1. Use \theorem, \definition, \example, and \proof environments
2. Number equations with \begin{{equation}} ... \end{{equation}}
3. Include diagrams with TikZ where appropriate
4. Structure sections logically with \section and \subsection
5. Include exercises at the end of the chapter

Make sure all mathematics is correct and notation is consistent.
"""
        
        # Generate content using Claude
        logger.info(f"Generating content for Chapter {chapter_number}: {chapter_title}")
        try:
            response = self.client.messages.create(
                model=self.config.get("model", "claude-3-7-sonnet-20250219"),
                max_tokens=100000,
                temperature=0.3,
                system="You are an expert mathematics professor writing a textbook chapter. Write in the style of Rudin/Atiyah Macdonald, balancing brevity with pedagogical clarity.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Extract content from response
            content = response.content[0].text
            
            # Process the content to fit the template if needed
            # (You might need to parse sections, introduction, etc.)
            
            # For now, we'll just use the raw content from Claude
            return content
            
        except Exception as e:
            logger.error(f"Error generating chapter content: {str(e)}")
            raise
    
    def process_chapter(self, chapter_number, chapter_title, outline_path=None, outline_text=None):
        """
        Process a chapter from outline to GitHub pull request
        
        Args:
            chapter_number (int): Chapter number
            chapter_title (str): Chapter title
            outline_path (str, optional): Path to outline file
            outline_text (str, optional): Direct outline text
            
        Returns:
            dict: Pull request information
        """
        # Get the outline
        outline = outline_text
        if outline_path and not outline:
            try:
                # Try GitHub first
                outline = self.github.get_file_content(outline_path)
                
                # If not in repo, try local file
                if not outline:
                    with open(outline_path, 'r') as f:
                        outline = f.read()
            except Exception as e:
                logger.error(f"Failed to read outline: {str(e)}")
                return None
        
        if not outline:
            logger.error("No outline provided")
            return None
        
        # Create a branch for this chapter
        branch_name = f"chapter-{chapter_number}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.github.create_branch(branch_name)
        logger.info(f"Created branch: {branch_name}")
        
        # Generate chapter content
        chapter_content = self.generate_chapter_content(chapter_number, chapter_title, outline)
        
        # Save to GitHub
        file_path = f"chapters/chapter{chapter_number}.tex"
        self.github.create_or_update_file(
            file_path=file_path,
            content=chapter_content,
            commit_message=f"Add Chapter {chapter_number}: {chapter_title}",
            branch=branch_name
        )
        logger.info(f"Committed chapter to {branch_name}")
        
        # Create pull request
        pr = self.github.create_pull_request(
            title=f"Chapter {chapter_number}: {chapter_title}",
            body=f"""
# Chapter {chapter_number}: {chapter_title}

This PR contains the generated content for Chapter {chapter_number}.

## Outline
```
{outline[:500]}... 
```
*(outline truncated for brevity)*

## Review Requested
- Mathematical accuracy
- Pedagogical clarity
- LaTeX formatting and structure
- Consistency with book style
            """,
            head_branch=branch_name
        )
        
        logger.info(f"Created PR #{pr['number']} for review")
        return pr


def main():
    """Main function to run the agent from command line"""
    parser = argparse.ArgumentParser(description="Generate a math textbook chapter and submit to GitHub")
    parser.add_argument("--repo-owner", required=True, help="GitHub repository owner")
    parser.add_argument("--repo-name", required=True, help="GitHub repository name")
    parser.add_argument("--chapter", required=True, type=int, help="Chapter number")
    parser.add_argument("--title", required=True, help="Chapter title")
    parser.add_argument("--outline", help="Path to outline file")
    parser.add_argument("--config", default="config.json", help="Path to configuration file")
    
    args = parser.parse_args()
    
    # Create the agent
    agent = ChapterWriterAgent(
        repo_owner=args.repo_owner,
        repo_name=args.repo_name,
        config_path=args.config
    )
    
    # Process the chapter
    outline_text = None
    if not args.outline:
        print("Enter chapter outline (end with Ctrl+D on Unix or Ctrl+Z on Windows):")
        outline_text = sys.stdin.read()
    
    result = agent.process_chapter(
        chapter_number=args.chapter,
        chapter_title=args.title,
        outline_path=args.outline,
        outline_text=outline_text
    )
    
    if result:
        print(f"Successfully created PR #{result['number']}: {result['html_url']}")
        return 0
    else:
        print("Failed to process chapter")
        return 1


if __name__ == "__main__":
    sys.exit(main())