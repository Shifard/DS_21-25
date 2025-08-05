import time
import requests
import csv
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import re # Make sure re is imported

# Base URL for the politics section
base_url = "https://www.gmanetwork.com/news/tracking/politics/"
# Set the desired number of articles to scrape
num_articles_to_scrape = 1600

# Initialize Selenium WebDriver for Chrome
# Make sure you have a compatible ChromeDriver executable in your PATH
driver = webdriver.Chrome()
driver.get(base_url)

# Define the path for the output CSV file
csv_file_path = 'gma_politics_news.csv'

# Open the CSV file in write mode
with open(csv_file_path, 'w', encoding='utf-8-sig', newline='') as csv_file:
    csv_writer = csv.writer(csv_file)
    # Write the header row
    csv_writer.writerow(['label', 'article'])

    articles_scraped = 0
    # Use a set to store scraped article URLs to avoid duplicates
    scraped_urls = set()
    # Flag to indicate if an article older than 2021 has been encountered
    found_older_article = False

    # Continue scraping until the desired number of articles is reached
    # or no more new content can be loaded by scrolling
    # or an older article is found (indicating we've scrolled past relevant content)
    while articles_scraped < num_articles_to_scrape and not found_older_article:
        print(f"Current articles scraped: {articles_scraped}")

        # Scroll down to the bottom of the page to load more content
        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.END)

        # Wait for new content to load after scrolling
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.ID, 'grid_thumbnail_stories'))
            )
            time.sleep(3)
        except TimeoutException:
            print("Timeout occurred while waiting for new content to load. No more content or slow loading.")
            break
        except NoSuchElementException:
            print("Element with ID 'grid_thumbnail_stories' not found. Page structure might have changed or no content.")
            break

        updated_page_source = driver.page_source
        soup_base = BeautifulSoup(updated_page_source, 'html.parser')

        main_articles_ul = soup_base.find('ul', id='grid_thumbnail_stories')

        if not main_articles_ul:
            print("Main article list (UL with id='grid_thumbnail_stories') not found. Exiting.")
            break

        article_list_items = main_articles_ul.find_all('li')

        for li_item in article_list_items:
            if found_older_article:
                break
            try:
                anchor_tag = li_item.find('a', class_='story_link')
                if anchor_tag and 'href' in anchor_tag.attrs:
                    article_link = anchor_tag['href']
                    if not article_link.startswith('http'):
                        article_link = f"https://www.gmanetwork.com{article_link}"

                    if article_link in scraped_urls:
                        continue
                    else:
                        scraped_urls.add(article_link)

                    print(f"Attempting to scrape: {article_link}")
                    response_article = requests.get(article_link, allow_redirects=True, timeout=10)

                    if response_article.status_code == 200:
                        soup_article = BeautifulSoup(response_article.text, 'html.parser')

                        # --- Date-time extraction and filtering ---
                        # First, try to find the time tag with datetime attribute (original method)
                        time_tag = soup_article.find('time', attrs={'datetime': True})
                        article_year = None
                        if time_tag and time_tag.has_attr('datetime'):
                            datetime_str = time_tag['datetime']
                            if len(datetime_str) >= 4:
                                article_year = datetime_str[:4]
                        
                        # If that fails, try the new method based on your snippet
                        # Find the div with class "article-date" and extract the year from its text
                        if not article_year:
                             date_div = soup_article.find('div', class_='article-date')
                             if date_div:
                                 date_text = date_div.get_text()
                                 # Use regex to find a year between 2021 and 2025
                                 year_match = re.search(r'\b(202[1-5])\b', date_text)
                                 if year_match:
                                     article_year = year_match.group(1)

                        # Check if the article year is within the desired range
                        if article_year and ('2021' <= article_year <= '2025'):
                            article_content_div = soup_article.find('div', class_='story_main')
                            if not article_content_div:
                                article_content_div = soup_article.find('div', class_='article-body')

                            if article_content_div:
                                paragraphs = article_content_div.find_all('p')
                                content_text = ' '.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])

                                if content_text:
                                    csv_writer.writerow(['1', content_text])
                                    articles_scraped += 1
                                    print(f"Scraped Article {articles_scraped} from {article_year}")

                                    if articles_scraped >= num_articles_to_scrape:
                                        break
                                else:
                                    print(f"No text content found in paragraphs for article: {article_link}")
                            else:
                                print(f"Could not find 'story_main' or 'article-body' for: {article_link}. Skipping.")
                        else:
                            print(f"Skipping article {article_link}: Published year is not 2021-2025 (found: {article_year if article_year else 'N/A'}). Stopping further scraping assuming ascending order.")
                            found_older_article = True
                            break

                    else:
                        print(f"Failed to retrieve article. Status code: {response_article.status_code} for {article_link}")

            except requests.exceptions.RequestException as req_err:
                print(f"Request error for {article_link}: {req_err}")
            except Exception as e:
                print(f"An error occurred while processing an article link: {e}")

        if found_older_article:
            break

print(f"Scraped {articles_scraped} articles. Data saved to {csv_file_path}")
driver.quit()