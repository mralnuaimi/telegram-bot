from telegram import Update, ForceReply
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import requests
from bs4 import BeautifulSoup
import asyncio
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from textwrap import wrap
import re
from datetime import datetime
import re
from nltk.tokenize import sent_tokenize  # Ensure you have nltk installed and downloaded the necessary data
import os
from openai import OpenAI

import os

# Retrieve sensitive keys from environment variables
telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
openai_api_key = os.getenv("OPENAI_API_KEY")

if not telegram_bot_token or not openai_api_key:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN or OPENAI_API_KEY in environment variables!")


openai_key = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=openai_key)

webhook_url = os.environ.get("WEBHOOK_URL")

# List of keywords to check against
keywords = set([
    "World", "Technology", "Space", "Economy", "Transportation", "Urbanism", "Health",
    "Nature", "Markets", "Energy", "Science", "Climate", "Politics", "Entertainment",
    "Aviation", "Sports", "Wealth", "Education", "Environment", "Real Estate", "Culture",
    "Business", "Defense", "Defence", "Crypto", "Travel", "Ancient History", "History",
    "Archaeology", "Investing", "Investment", "Gaming", "Government", "Workforce",
    "Weather", "Finance", "Infrastructure", "Architecture", "Society"
])

# Define the URL pattern
url_pattern = re.compile(r'https?://\S+')

# Function to create the daily brief image
def create_daily_brief_image(date_str):
    img = Image.new('RGB', (1080, 1920), color='black')
    draw = ImageDraw.Draw(img)
    font_path_h = "fonts/ProximaNova-Bold.ttf"
    font_path_sh = "fonts/ProximaNova-Regular.ttf"
    font_size_h = 45
    font_h = ImageFont.truetype(font_path_sh, font_size_h)
    font_size_sh = 110
    font_sh = ImageFont.truetype(font_path_h, font_size_sh)
    date_font_size = 45
    date_font = ImageFont.truetype(font_path_sh, date_font_size)

    # Text content
    greetings = "GOOD MORNING YOUR HIGHNESS"
    brief = "Your Daily Brief"
    today_date = date_str  # Use the provided date string


    # Calculate text positioning
    text_y = 800
    draw.text((100, text_y), greetings, font=font_h, fill='white')
    text_y += 70
    draw.text((100, text_y), brief, font=font_sh, fill='white')
    text_y += 160
    draw.text((110, text_y), today_date, font=date_font, fill='white')

    return img

def draw_rounded_rectangle(draw, rect, radius, fill):
    """Draw a rounded rectangle"""
    left, top, right, bottom = rect
    draw.pieslice([left, top, left + radius * 2, top + radius * 2], 180, 270, fill=fill)
    draw.pieslice([right - radius * 2, top, right, top + radius * 2], 270, 360, fill=fill)
    draw.pieslice([left, bottom - radius * 2, left + radius * 2, bottom], 90, 180, fill=fill)
    draw.pieslice([right - radius * 2, bottom - radius * 2, right, bottom], 0, 90, fill=fill)
    draw.rectangle([left + radius, top, right - radius, bottom], fill=fill)
    draw.rectangle([left, top + radius, right, bottom - radius], fill=fill)

def draw_bullet_points(draw_bullets, start_bullet_points_y, font_b, bullet_points, image_width):
    bullet_radius = 10
    bullet_indent = 120  # Indent for the bullet circle
    text_indent = bullet_indent + 20  # Indent for the text
    y_offset = start_bullet_points_y
    line_spacing = 10  # Space between lines
    Par_spacing = 30

    for point in bullet_points:
        # Wrap the text for each bullet point to fit within the image width
        wrapped_text = wrap(point, width=35)
        
        for line in wrapped_text:
            # Calculate vertical center for the bullet if it's the first line of text
            if line == wrapped_text[0]:
                bullet_center_y = y_offset + font_b.getbbox(line)[3] // 2
                # Draw the bullet circle
                draw_bullets.ellipse([bullet_indent - bullet_radius, bullet_center_y - bullet_radius,
                              bullet_indent + bullet_radius, bullet_center_y + bullet_radius], fill='white')

            # Draw the text
            draw_bullets.text((text_indent, y_offset), line, font=font_b, fill='white')
            y_offset += font_b.getbbox(line)[3] + line_spacing  # Move down to the next line
        y_offset += Par_spacing  # Additional space after each bullet point

# Regex to detect URLs
def contains_url(text):
    # Search text for URLs
    match = url_pattern.search(text)
    return match is not None

# Function to categorize input parts
def categorize_input(parts):
    url = None
    keyword = None
    bullet_points = []

    for part in parts:
        cleaned_part = part.strip()  # Trim whitespace
        if url_pattern.match(cleaned_part):  # Check if it's a URL
            url = cleaned_part
        elif cleaned_part in keywords:  # Check if it's a known keyword
            keyword = cleaned_part
        else:
            # Remove leading dashes and spaces from bullet points
            cleaned_bullet_point = re.sub(r'^(-\s+|\d+\.\s+|\*\s+)', '', cleaned_part)
            bullet_points.append(cleaned_bullet_point)

    return url, keyword, bullet_points

# Async function to scrape Open Graph data with improved handling
async def scrape_og_data(url: str) -> tuple:
    try:
        # Mimic a request from Google Chrome to avoid blocks
        response = await asyncio.to_thread(requests.get, url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.85 Safari/537.36'})
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Attempt to find Open Graph tags or other relevant meta tags
            og_image = soup.find('meta', property='og:image') or \
                       soup.find('meta', attrs={'name': 'og:image'}) or \
                       soup.find('meta', attrs={'name': 'twitter:image'}) or \
                       soup.find('meta', attrs={'property': 'twitter:image'})
            
            og_title = soup.find('meta', property='og:title') or \
                       soup.find('meta', attrs={'name': 'og:title'}) or \
                       soup.find('meta', attrs={'name': 'twitter:title'}) or \
                       soup.find('meta', attrs={'property': 'twitter:title'})
            
            image_url = og_image['content'] if og_image and 'content' in og_image.attrs else None
            title_text = og_title['content'] if og_title and 'content' in og_title.attrs else 'No title found'

            # Clean the title by removing everything after the first '|'
            title_text = title_text.split(" | ")[0] if title_text else 'No title found'
            
            if not image_url:
                return (None, "No Open Graph image found.")
            if not title_text:
                return (None, "No Open Graph title found.")
            return (image_url, title_text)
        else:
            return (None, f'Failed to retrieve URL. Status code: {response.status_code}')
    except Exception as e:
        return (None, f'Exception occurred: {str(e)}')




# Function to create and return an image with the title and a keyword
async def create_story_image(title: str, keyword: str, image_url: str, bullet_points=None) -> BytesIO:
    title = title.upper()
    response = requests.get(image_url)
    img = Image.open(BytesIO(response.content))
    
    # Calculate the new height to maintain aspect ratio and match the page width
    aspect_ratio = img.height / img.width
    new_height = int(1080 * aspect_ratio)

    # Resize the image to fit the page width while maintaining aspect ratio
    img = img.resize((1080, new_height), Image.Resampling.LANCZOS)

    title_bg_height = 700
    title_img = Image.new('RGB', (1080, title_bg_height), color='black')
    draw = ImageDraw.Draw(title_img)
    font_path = "fonts/OpenSans-Bold.ttf"
    font_size = 70
    font = ImageFont.truetype(font_path, font_size)
    keyword_font = ImageFont.truetype(font_path, 50)  # Smaller font size for keyword

    keyword = keyword.upper()
    # Measure the keyword
    keyword_bbox = draw.textbbox((0, 0), keyword, font=keyword_font)  # Measure text from the origin for accurate size
    keyword_width = keyword_bbox[2] - keyword_bbox[0]
    keyword_height = keyword_bbox[3] - keyword_bbox[1]

    # Padding around the text
    horizontal_padding = 20
    vertical_padding = 20  # You can increase or decrease this for more or less space above and below the text

    # Calculate the box dimensions including padding
    total_width = keyword_width + 2 * horizontal_padding
    total_height = keyword_height + 2 * vertical_padding

    # Position the rectangle 100 pixels from the left
    left_margin = 100
    top_margin = 0  # This top margin can be adjusted to move the box up or down on the image

    # Draw the rounded rectangle
    draw_rounded_rectangle(draw, [left_margin, top_margin, left_margin + total_width, top_margin + total_height], 30, 'white')

    # Draw the text inside the rectangle
    # Adjust text_y to move the text up or down within the box
    text_x = left_margin + horizontal_padding
    text_y = top_margin + 5  # Adjust this value to change vertical text positioning within the box
    draw.text((text_x, text_y), keyword, font=keyword_font, fill='black')

    # Draw the title below the keyword
    current_h = keyword_height + 50
    wrapped_text = wrap(title, width=20)
    for line in wrapped_text:
        line_bbox = draw.textbbox((100, current_h), line, font=font)
        draw.text((100, current_h), line, font=font, fill='white')
        current_h += line_bbox[3] - line_bbox[1] + 10

    # Finalize the main image
    final_img = Image.new('RGB', (1080, 1920), 'black')
    final_img.paste(title_img, (0, 300))
    image_x_position = (1080 - img.width) // 2
    final_img.paste(img, (image_x_position, title_bg_height + 300))
    img_byte_arr = BytesIO()
    final_img.save(img_byte_arr, format='JPEG')
    img_byte_arr.seek(0)

  # Prepare and draw bullet points on a new image if provided
    bullet_img_byte_arr = None
    if bullet_points:
        bullet_img = Image.new('RGB', (1080, 1920), 'black')
        draw_bullets = ImageDraw.Draw(bullet_img)
        bullet_img.paste(title_img, (0, 150))  # Paste the title area to the bullet image
        bullet_y = current_h + 200  # Start drawing bullets slightly below the title
        font_path_b = "fonts/ProximaNova-Regular.ttf"
        font_size_b = 50
        font_b = ImageFont.truetype(font_path_b, font_size_b)
        image_width = 1080  # Width of the image being drawn on
        start_bullet_points_y = bullet_y  # Vertical start position for bullet points
        draw_bullet_points(draw_bullets, start_bullet_points_y, font_b, bullet_points, image_width)
        bullet_img_byte_arr = BytesIO()
        bullet_img.save(bullet_img_byte_arr, format='JPEG')
        bullet_img_byte_arr.seek(0)

    return [img_byte_arr, bullet_img_byte_arr] if bullet_points else [img_byte_arr]

def extract_main_content(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Attempt to find the article tag or main content div
    possible_content_selectors = [
        'article',  # Common article tag
        'div.post-content',  # Common class names for article content
        'div.article-body',  # Other possible class names
        'div.entry-content',  # Other possible class names
        'div.content-body',  # Other possible class names
        'div.main-content',  # Other possible class names
    ]
    
    for selector in possible_content_selectors:
        article_content = soup.select_one(selector)
        if article_content:
            break
    else:
        article_content = soup.body

    # Extract text from all paragraph tags within the identified main content
    paragraphs = article_content.find_all('p')
    article_text = ' '.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
    
    return article_text


async def fetch_article_content(url: str):
    response = await asyncio.to_thread(requests.get, url)
    if response.status_code == 200: 
        # Here you extract the content from the response, this might involve parsing HTML
        return extract_main_content(response.text)  # Define this function based on how you want to extract content
    return ""

# Respond to messages
async def auto_process_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text.strip()
    parts = re.split(r'\n+', message_text)  # Splitting parts by new lines

    url, keyword, bullet_points = categorize_input(parts)

    # Call summarization if fewer than three bullet points are provided
    if len(bullet_points) < 3 and url:
        article_content = await fetch_article_content(url)  # You need to define this function
        summarized_points = await summarize_with_chatgpt(article_content)
        bullet_points = summarized_points if summarized_points else ["Failed to summarize"]
       
    # Attempt to further refine bullet points if not explicitly clear
    if len(bullet_points) > 3:
        sentences = []
        for point in bullet_points:
            sentences.extend(sent_tokenize(point))  # Break down each part into sentences
        bullet_points = sentences[:3]  # Take the first three sentences as bullet points

    if url:
        image_url, title = await scrape_og_data(url)
        if image_url:
            category = await classify_headline_with_chatgpt(title)
            images = await create_story_image(title, category, image_url, bullet_points)
            for img in images:
                await update.message.reply_photo(photo=img)
        else:
            await update.message.reply_text("Error retrieving Open Graph data.")
    else:
        await update.message.reply_text("Please include a valid URL in your message.")


async def summarize_with_chatgpt(content: str):
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a media reporter for the government. You will be presented with articles that you need to summarize in short key points."},
            {"role": "user", "content": f"Summarize this article into three short bullet points, each with minimum 20 words and maximum 27 words:\n\n{content}"}
        ]
    )

    # Extract the generated text from the completion correctly
    if completion.choices:
        # Strip leading "- " from each summary line if present
        summary = [line.lstrip('- ').strip() for line in completion.choices[0].message.content.strip().split('\n')]
        return summary
    else:
        return ["Failed to generate summary."]

# Function to classify the headline using ChatGPT
async def classify_headline_with_chatgpt(headline: str):
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are an AI assistant that classifies news headlines into predefined categories."},
            {"role": "user", "content": f"Read the following headline, and select one word exclusively from the following categories to represent the headline category (give one-word answer only): World, Technology, Space, Economy, Transportation, Urbanism, Health, Nature, Markets, Energy, Science, Climate, Politics, Entertainment, Aviation, Sports, Wealth, Education, Environment, Culture, Business, Defense, Defence, Crypto, Travel, History, Archaeology, Investing, Investment, Gaming, Government, Workforce, Weather, Finance, Infrastructure, Architecture, Society.\n\nHeadline: {headline}"}
        ]
    )

    if completion.choices:
        category = completion.choices[0].message.content.strip()
        return category
    else:
        return "Uncategorized"


# Command handler for '/today'
async def today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if args:
        date_input = " ".join(args)
        try:
            # Try to parse the date provided by the user
            date_obj = datetime.strptime(date_input, '%d-%m-%y')  # Parse input date format
            date_str = date_obj.strftime('%-d %b, %Y')  # Format output date
        except ValueError:
            await update.message.reply_text('Please provide the date in the format "dd-mm-yy". Example: /today 27-04-24')
            return
    else:
        # Use today's date if no date is provided
        date_obj = datetime.now()
        date_str = date_obj.strftime('%-d %b, %Y')

    img = create_daily_brief_image(date_str)
    bio = BytesIO()
    img.save(bio, format='JPEG')
    bio.seek(0)
    await update.message.reply_photo(photo=bio)


# Main function to handle the commands
async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Hello! Send me a URL and a keyword, and I will fetch the Open Graph image and title!')

# Command handler for '/help'
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "Welcome to the CPNews Bot, Here are the commands you can use:\n\n"
        "/today [dd-mm-yy] - Get the daily brief for today or a specific date.\n"
        "\n"
        "To send news URLs and get your news posts:\n"
        "1. Send a URL.\n"
        "2. Optionally, include keywords and bullet points.\n"
        "\n"
        "Example message format:\n"
        "https://example.com/article\n"
        "Technology\n"
        "- Bullet point 1\n"
        "- Bullet point 2\n"
        "- Bullet point 3\n"
    )
    await update.message.reply_text(help_text)

# Setup the application
telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
app = ApplicationBuilder().token(telegram_token).build()
app.add_handler(CommandHandler("hello", hello))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), auto_process_message))
# Adding command handler for '/today'
app.add_handler(CommandHandler('today', today))
app.add_handler(CommandHandler('help', help_command))

app.run_webhook(
    listen="0.0.0.0",
    port=int(os.environ.get("PORT", 8443)),
    url_path=telegram_bot_token,
    webhook_url=f"{os.environ.get('RENDER_EXTERNAL_URL')}/{telegram_bot_token}"
)
