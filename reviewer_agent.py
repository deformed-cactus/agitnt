"""
Reviewer Agent for Multi-AI Book Writing System

This script implements an agent that reviews mathematical content, checking for
accuracy, pedagogical effectiveness, and consistency with the desired style.

The agent:
1. Retrieves chapter content from pull requests
2. Analyzes the content for mathematical accuracy
3. Provides feedback on clarity, examples, and pedagogy
4. Suggests improvements via GitHub comments
5. Can integrate feedback from multiple AI systems

Usage:
    python reviewer_agent.py --repo-owner username --repo-name math-book-project --pr 42
"""

import os
import argparse
import logging
import sys
import json
import re
import tempfile
import anthropic
from github_agent import GitHubAgent
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("reviewer.log"), logging.StreamHandler()]
)
logger = logging.getLogger("reviewer_agent")

class ReviewerAgent:
    """Agent for reviewing mathematical content"""
    
    def __init__(self, repo_owner, repo_name, config_path="config.json"):
        """
        Initialize the reviewer agent
        
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
            agent_name=self.config.get("agent_name", "ReviewerAgent")
        )
        
        # Initialize Claude client if API key is available
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            self.anthropic_client = anthropic.Anthropic(api_key=api_key)
        else:
            logger.warning("No Anthropic API key found, Claude integration unavailable")
            self.anthropic_client = None
        
        # Initialize other AI clients if configured
        self._initialize_other_ais()
        
        logger.info(f"Initialized ReviewerAgent for {repo_owner}/{repo_name}")
    
    def _initialize_other_ais(self):
        """Initialize clients for other AI systems (Grok, OpenAI, etc.)"""
        # This is a placeholder - in a real implementation, you would initialize
        # the clients for other AI systems based on your configuration
        
        # Examples (not implemented):
        # self.openai_client = None
        # self.grok_client = None
        
        # If "other_ais" is in the config, try to initialize them
        other_ais = self.config.get("other_ais", [])
        for ai_config in other_ais:
            ai_name = ai_config.get("name")
            api_key_env = ai_config.get("api_key_env")
            
            if not ai_name or not api_key_env:
                continue
                
            api_key = os.getenv(api_key_env)
            if not api_key:
                logger.warning(f"No API key found for {ai_name}, integration unavailable")
                continue
                
            logger.info(f"Initialized {ai_name} integration")
            
            # In a real implementation, you would initialize the client here
            # based on the AI system type
    
    def load_config(self, config_path):
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
            logger.info(f"Loaded configuration from {config_path}")
        except FileNotFoundError:
            logger.warning(f"Configuration file {config_path} not found. Using defaults.")
            self.config = {
                "agent_name": "ReviewerAgent",
                "model": "claude-3-7-sonnet-20250219",
                "style_guide": "math_style_guide.md",
                "review_categories": [
                    "mathematical_accuracy",
                    "pedagogical_clarity",
                    "examples",
                    "exercises",
                    "notation_consistency"
                ],
                "detailed_feedback": True,
                "other_ais": [
                    {
                        "name": "OpenAI",
                        "api_key_env": "OPENAI_API_KEY",
                        "model": "gpt-4",
                        "review_categories": ["pedagogical_clarity", "examples"]
                    },
                    {
                        "name": "Grok",
                        "api_key_env": "GROK_API_KEY",
                        "model": "grok-3",
                        "review_categories": ["mathematical_accuracy", "notation_consistency"]
                    }
                ],
                "review_template": "review_template.md"
            }
    
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
    
    def _get_review_template(self):
        """Get the review template"""
        template_path = self.config.get("review_template", "review_template.md")
        
        # Try to get from GitHub first
        content = self.github.get_file_content(template_path)
        if content:
            return content
        
        # If not found, return default template
        return """
# Chapter Review: {chapter_title}

## Overall Assessment
{overall_assessment}

## Mathematical Accuracy
**Rating**: {math_accuracy_rating}

{math_accuracy_feedback}

## Pedagogical Clarity
**Rating**: {pedagogical_clarity_rating}

{pedagogical_clarity_feedback}

## Examples
**Rating**: {examples_rating}

{examples_feedback}

## Exercises
**Rating**: {exercises_rating}

{exercises_feedback}

## Notation and Consistency
**Rating**: {notation_consistency_rating}

{notation_consistency_feedback}

## Specific Suggestions
{specific_suggestions}

## Summary
{summary}
"""
    
    def get_pull_request_content(self, pr_number):
        """
        Get the content of files in a pull request
        
        Args:
            pr_number (int): Pull request number
            
        Returns:
            dict: Dictionary of files and their content
        """
        try:
            # This would require additional GitHub API methods to:
            # 1. Get the PR details to find the branch
            # 2. Get the list of files changed in the PR
            # 3. Get the content of each file
            
            logger.info(f"Getting content from PR #{pr_number}")
            
            # Get the PR details to find the branch
            pr_info = self.github._make_request("GET", f"/pulls/{pr_number}")
            if not pr_info:
                logger.error(f"Could not find PR #{pr_number}")
                return None
            
            # Get the head branch
            head_branch = pr_info["head"]["ref"]
            logger.info(f"PR #{pr_number} is from branch {head_branch}")
            
            # Get the PR title
            pr_title = pr_info["title"]
            
            # Get the list of files changed in the PR
            files_endpoint = f"/pulls/{pr_number}/files"
            changed_files = self.github._make_request("GET", files_endpoint)
            
            if not changed_files:
                logger.error(f"Could not get files changed in PR #{pr_number}")
                return None
            
            # Process each file
            result = {}
            for file_info in changed_files:
                file_path = file_info["filename"]
                
                # Skip non-tex files or files outside the chapters directory
                if not file_path.endswith(".tex") or not file_path.startswith("chapters/"):
                    continue
                
                # Get the content from the branch
                content = self.github.get_file_content(file_path, head_branch)
                if content:
                    result[file_path] = content
                else:
                    logger.warning(f"Could not find content for {file_path} in branch {head_branch}")
            
            if not result:
                logger.error(f"No chapter files found in PR #{pr_number}")
                return None
            
            # Extract chapter title from PR title
            chapter_title = pr_title
            match = re.match(r"Chapter \d+:?\s*(.*?)$", pr_title)
            if match:
                chapter_title = match.group(1).strip()
            
            # Add PR title to the result
            result["__pr_title__"] = chapter_title
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting PR content: {str(e)}")
            return None
    
    def review_with_claude(self, content, chapter_title="Unknown"):
        """
        Use Claude to review the chapter content
        
        Args:
            content (str): Chapter content in LaTeX
            chapter_title (str): Title of the chapter
            
        Returns:
            dict: Review results by category
        """
        if not self.anthropic_client:
            logger.error("Claude integration unavailable")
            return None
        
        # Get style guide
        style_guide = self._get_style_guide()
        
        # Construct prompt for Claude
        prompt = f"""
You are reviewing a mathematics textbook chapter titled "{chapter_title}". 
You're an expert mathematician and educator tasked with providing detailed, constructive feedback.

# Chapter Content (LaTeX):
```latex
{content[:50000]}  # Limit to avoid exceeding context window
```

# Writing Style Guide:
{style_guide}

# Review Task:
Please review this chapter carefully and provide specific feedback in the following categories:

1. Mathematical Accuracy:
   - Are all definitions, theorems, and proofs mathematically correct?
   - Are there any logical errors or gaps in reasoning?
   - Are all necessary conditions stated clearly?

2. Pedagogical Clarity:
   - Is the content explained clearly and accessibly?
   - Are concepts introduced in a logical progression?
   - Is there sufficient motivation for new concepts?

3. Examples:
   - Are the examples effective in illustrating the concepts?
   - Are there enough examples of varying difficulty?
   - Do examples show both standard cases and edge cases?

4. Exercises:
   - Are the exercises appropriate for reinforcing the material?
   - Do they progress appropriately in difficulty?
   - Do they cover all key concepts in the chapter?

5. Notation and Consistency:
   - Is notation used consistently throughout?
   - Is the notation standard for the field?
   - Are all symbols defined before use?

For each category, provide:
1. An overall assessment (Excellent, Good, Needs Improvement, Poor)
2. Specific examples from the text to support your assessment
3. Concrete suggestions for improvement

Structure your feedback to be actionable, specific, and constructive. Include line numbers or section references where possible.
"""

        try:
            # Generate review using Claude
            logger.info(f"Generating review for chapter '{chapter_title}' using Claude")
            response = self.anthropic_client.messages.create(
                model=self.config.get("model", "claude-3-7-sonnet-20250219"),
                max_tokens=40000,
                temperature=0.0,  # Use zero temperature for more consistent reviews
                system="You are an expert mathematician and educator reviewing a textbook chapter. Provide detailed, specific, and actionable feedback that maintains mathematical rigor while improving pedagogical effectiveness.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Extract content from response
            review_content = response.content[0].text
            
            # Parse review into categories
            # This is a simplified parsing - in a real implementation, you'd want
            # to use more robust parsing based on the actual structure of Claude's response
            categories = {}
            
            # Extract overall assessment
            overall_match = re.search(r"# Overall Assessment\s+(.*?)(?=\s+#|$)", review_content, re.DOTALL)
            if overall_match:
                categories["overall"] = overall_match.group(1).strip()
            
            # Extract category-specific feedback
            for category in ["Mathematical Accuracy", "Pedagogical Clarity", "Examples", "Exercises", "Notation and Consistency"]:
                category_key = category.lower().replace(" ", "_")
                
                # Look for the category heading
                pattern = rf"# {re.escape(category)}\s+(?:\*\*Rating\*\*:?\s+([^\n]+))?\s+(.*?)(?=\s+#|$)"
                match = re.search(pattern, review_content, re.DOTALL)
                
                if match:
                    rating = match.group(1).strip() if match.group(1) else "No rating provided"
                    feedback = match.group(2).strip()
                    
                    categories[category_key] = {
                        "rating": rating,
                        "feedback": feedback
                    }
            
            # If we couldn't parse structured categories, return the full review
            if not categories:
                return {"full_review": review_content}
            
            # Add the full review as well
            categories["full_review"] = review_content
            
            return categories
            
        except Exception as e:
            logger.error(f"Error generating review with Claude: {str(e)}")
            return None
    
    def review_with_other_ai(self, content, chapter_title, ai_config):
        """
        Use another AI system to review the chapter content
        
        Args:
            content (str): Chapter content in LaTeX
            chapter_title (str): Title of the chapter
            ai_config (dict): Configuration for the AI system
            
        Returns:
            dict: Review results
        """
        # This is a placeholder - in a real implementation, you would
        # integrate with the specific AI system based on your configuration
        
        ai_name = ai_config.get("name", "Unknown AI")
        logger.info(f"Would review with {ai_name} (not implemented)")
        
        # Return a placeholder result
        return {
            "rating": "Not Implemented",
            "feedback": f"Review with {ai_name} is not implemented yet."
        }
    
    def combine_reviews(self, claude_review, other_reviews):
        """
        Combine reviews from different AI systems
        
        Args:
            claude_review (dict): Review from Claude
            other_reviews (dict): Reviews from other AI systems
            
        Returns:
            dict: Combined review
        """
        # Start with Claude's review as the base
        combined = claude_review.copy() if claude_review else {}
        
        # Add insights from other AI systems
        for ai_name, review in other_reviews.items():
            if not review:
                continue
                
            # For each review category, add insights from this AI
            for category, content in review.items():
                category_key = f"{category}_insights"
                
                if category_key not in combined:
                    combined[category_key] = {}
                
                combined[category_key][ai_name] = content
        
        return combined
    
    def format_review_for_comment(self, review, chapter_title):
        """
        Format the review for posting as GitHub comments
        
        Args:
            review (dict): Review data
            chapter_title (str): Title of the chapter
            
        Returns:
            list: List of comments to post
        """
        # If we have a full review, just return it
        if "full_review" in review and not self.config.get("detailed_feedback", True):
            return [review["full_review"]]
        
        # Otherwise, format a structured review
        template = self._get_review_template()
        
        # Format the overall review
        formatted_review = template.format(
            chapter_title=chapter_title,
            overall_assessment=review.get("overall", "No overall assessment provided."),
            math_accuracy_rating=review.get("mathematical_accuracy", {}).get("rating", "Not rated"),
            math_accuracy_feedback=review.get("mathematical_accuracy", {}).get("feedback", "No feedback provided."),
            pedagogical_clarity_rating=review.get("pedagogical_clarity", {}).get("rating", "Not rated"),
            pedagogical_clarity_feedback=review.get("pedagogical_clarity", {}).get("feedback", "No feedback provided."),
            examples_rating=review.get("examples", {}).get("rating", "Not rated"),
            examples_feedback=review.get("examples", {}).get("feedback", "No feedback provided."),
            exercises_rating=review.get("exercises", {}).get("rating", "Not rated"),
            exercises_feedback=review.get("exercises", {}).get("feedback", "No feedback provided."),
            notation_consistency_rating=review.get("notation_consistency", {}).get("rating", "Not rated"),
            notation_consistency_feedback=review.get("notation_consistency", {}).get("feedback", "No feedback provided."),
            specific_suggestions=review.get("specific_suggestions", "No specific suggestions provided."),
            summary=review.get("summary", "No summary provided.")
        )
        
        # Split into sections if the review is too long for a single comment
        # GitHub has a limit of around 65536 characters per comment
        if len(formatted_review) < 60000:
            return [formatted_review]
        
        # Split into sections
        sections = []
        
        # Add an overview
        overview = f"""
# Chapter Review: {chapter_title}

## Overall Assessment
{review.get("overall", "No overall assessment provided.")}

This review is split into multiple comments due to length. See below for detailed feedback.
"""
        sections.append(overview)
        
        # Add each category as a separate comment
        categories = [
            ("Mathematical Accuracy", "mathematical_accuracy"),
            ("Pedagogical Clarity", "pedagogical_clarity"),
            ("Examples", "examples"),
            ("Exercises", "exercises"),
            ("Notation and Consistency", "notation_consistency")
        ]
        
        for title, key in categories:
            if key in review:
                section = f"""
## {title}
**Rating**: {review[key].get("rating", "Not rated")}

{review[key].get("feedback", "No feedback provided.")}
"""
                sections.append(section)
        
        # Add specific suggestions and summary
        if "specific_suggestions" in review or "summary" in review:
            final_section = "## Final Notes\n\n"
            
            if "specific_suggestions" in review:
                final_section += f"### Specific Suggestions\n{review['specific_suggestions']}\n\n"
                
            if "summary" in review:
                final_section += f"### Summary\n{review['summary']}"
                
            sections.append(final_section)
        
        return sections
    
    def post_review_comments(self, pr_number, review, chapter_title):
        """
        Post review comments to the pull request
        
        Args:
            pr_number (int): Pull request number
            review (dict): Review results
            chapter_title (str): Title of the chapter
            
        Returns:
            bool: Success status
        """
        try:
            # Format the review for comments
            comments = self.format_review_for_comment(review, chapter_title)
            
            if not comments:
                logger.error("No comments to post")
                return False
            
            # Post each comment
            for comment in comments:
                # Truncate if too long (GitHub has limits)
                if len(comment) > 60000:
                    comment = comment[:59997] + "..."
                
                self.github.comment_on_pull_request(pr_number, comment)
            
            logger.info(f"Posted {len(comments)} review comments to PR #{pr_number}")
            return True
            
        except Exception as e:
            logger.error(f"Error posting review comments: {str(e)}")
            return False
    
    def add_inline_comments(self, pr_number, review, content):
        """
        Add inline comments to specific parts of the chapter
        
        Args:
            pr_number (int): Pull request number
            review (dict): Review results
            content (dict): Dictionary of files and their content
            
        Returns:
            bool: Success status
        """
        # This is a more advanced feature that would require:
        # 1. Parsing the review to extract specific line-level feedback
        # 2. Using GitHub's API to add comments to specific lines in the PR
        
        # For now, we'll just provide a placeholder implementation
        logger.info("Inline comments feature not fully implemented")
        
        # Example of how you might implement this:
        # 1. Extract comments from the review that reference specific lines
        # 2. For each comment, determine the file and line number
        # 3. Use GitHub API to add a comment to that specific line
        
        # In a real implementation, you might use a more structured approach
        # to have the AI specifically identify line-level issues
        
        return True
    
    def create_latex_diff(self, original_content, suggested_changes):
        """
        Create a LaTeX diff file showing suggested changes
        
        Args:
            original_content (str): Original LaTeX content
            suggested_changes (dict): Suggested changes by line number
            
        Returns:
            str: Path to the diff file
        """
        # This is a more advanced feature that would require:
        # 1. Parsing the original content into lines
        # 2. Applying the suggested changes
        # 3. Creating a diff file showing the changes
        
        # For now, we'll just provide a placeholder implementation
        logger.info("LaTeX diff feature not fully implemented")
        
        # Create a temporary file to store the diff
        fd, diff_path = tempfile.mkstemp(suffix=".tex")
        os.close(fd)
        
        # Write a placeholder diff
        with open(diff_path, 'w') as f:
            f.write(r"""
% This is a placeholder diff file showing suggested changes
\documentclass{article}
\usepackage{color}
\usepackage{soul}
\usepackage{xcolor}

\newcommand{\add}[1]{\textcolor{green}{#1}}
\newcommand{\remove}[1]{\textcolor{red}{\st{#1}}}

\begin{document}
\section*{Suggested Changes}

Original: \remove{$f(x) = x^2$}

Suggested: \add{$f(x) = x^2 + C$}

% More suggested changes would be shown here
\end{document}
""")
        
        return diff_path
    
    def review_pull_request(self, pr_number):
        """
        Review a pull request
        
        Args:
            pr_number (int): Pull request number
            
        Returns:
            bool: Success status
        """
        try:
            # Get the content of the pull request
            content = self.get_pull_request_content(pr_number)
            if not content:
                logger.error("Failed to get pull request content")
                return False
            
            # Extract chapter title
            chapter_title = content.pop("__pr_title__", "Unknown Chapter")
            
            # Combine all chapter files into a single text for review
            combined_content = ""
            for file_path, file_content in content.items():
                combined_content += f"\n% File: {file_path}\n{file_content}\n"
            
            # Review with Claude
            claude_review = self.review_with_claude(combined_content, chapter_title)
            
            # Review with other AI systems if configured
            other_reviews = {}
            for ai_config in self.config.get("other_ais", []):
                ai_name = ai_config.get("name")
                if not ai_name:
                    continue
                    
                review = self.review_with_other_ai(combined_content, chapter_title, ai_config)
                if review:
                    other_reviews[ai_name] = review
            
            # Combine the reviews
            combined_review = self.combine_reviews(claude_review, other_reviews)
            
            # Post the review comments
            success = self.post_review_comments(pr_number, combined_review, chapter_title)
            
            # Add inline comments if configured
            if self.config.get("inline_comments", False):
                self.add_inline_comments(pr_number, combined_review, content)
            
            # Create and upload a LaTeX diff if configured
            if self.config.get("latex_diff", False) and "suggested_changes" in combined_review:
                diff_path = self.create_latex_diff(combined_content, combined_review["suggested_changes"])
                if diff_path:
                    # Upload the diff file
                    # In a real implementation, you would upload this to the repository
                    os.remove(diff_path)
            
            return success
            
        except Exception as e:
            logger.error(f"Error reviewing pull request: {str(e)}")
            return False


def main():
    """Main function to run the agent from command line"""
    parser = argparse.ArgumentParser(description="Review mathematical content in a pull request")
    parser.add_argument("--repo-owner", required=True, help="GitHub repository owner")
    parser.add_argument("--repo-name", required=True, help="GitHub repository name")
    parser.add_argument("--pr", required=True, type=int, help="Pull request number")
    parser.add_argument("--config", default="config.json", help="Path to configuration file")
    
    args = parser.parse_args()
    
    # Create the agent
    agent = ReviewerAgent(
        repo_owner=args.repo_owner,
        repo_name=args.repo_name,
        config_path=args.config
    )
    
    # Review the pull request
    success = agent.review_pull_request(args.pr)
    
    if success:
        print(f"Successfully reviewed PR #{args.pr}")
        return 0
    else:
        print(f"Failed to review PR #{args.pr}")
        return 1


if __name__ == "__main__":
    sys.exit(main())