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

# Base URL for the Philstar politics section
base_url = "https://www.philstar.com/tags/politics"
# Set the desired number of articles to scrape
# This can be set to a high number, as the script will stop once it hits older articles.
num_articles_to_scrape = 1000 # Example: Adjust as needed

# Initialize Selenium WebDriver for Chrome
# Make sure you have a compatible ChromeDriver executable in your PATH
driver = webdriver.Chrome()
driver.get(base_url)

# Define the path for the output CSV file
csv_file_path = 'philstar_politics_news.csv'

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

    # Main loop to scroll and scrape articles
    while articles_scraped < num_articles_to_scrape and not found_older_article:
        print(f"Current articles scraped: {articles_scraped}")

        # Scroll down to the bottom of the page to load more content
        # This simulates a user scrolling
        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.END)

        # Wait for the main news container to be present after scrolling
        # The new articles usually load within this div.
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.ID, 'news_main'))
            )
            # A short pause to ensure all dynamic content is rendered
            time.sleep(3)
        except TimeoutException:
            print("Timeout occurred while waiting for 'news_main' content to load. No more content or slow loading.")
            break # Exit loop if no new content loads within timeout
        except NoSuchElementException:
            print("Element with ID 'news_main' not found. Page structure might have changed or no content.")
            break

        # Get the updated page source after scrolling and loading
        updated_page_source = driver.page_source
        # Parse the page source with BeautifulSoup
        soup_base = BeautifulSoup(updated_page_source, 'html.parser')

        # Find the main div that contains the news listings
        main_news_div = soup_base.find('div', id='news_main')

        if not main_news_div:
            print("Main news div with id='news_main' not found. Exiting.")
            break

        # Find all elements with class 'titleForFeature' which contain the article links
        # This seems to be a common class for individual news entries on Philstar tag pages.
        article_link_containers = main_news_div.find_all('div', class_='titleForFeature')

        # Iterate through each found article container to get the link
        for container in article_link_containers:
            if found_older_article: # Check flag inside the inner loop to stop immediately
                break
            try:
                # Find the anchor tag within the current container
                anchor_tag = container.find('a', href=True) # Ensure it has an href attribute
                if anchor_tag:
                    article_link = anchor_tag['href']

                    # Check if the article URL has already been scraped to avoid duplicates
                    if article_link in scraped_urls:
                        continue # Skip if already scraped
                    else:
                        scraped_urls.add(article_link) # Add to the set of scraped URLs

                    print(f"Attempting to scrape: {article_link}")

                    # Use requests to get the content of the individual article page
                    response_article = requests.get(article_link, allow_redirects=True, timeout=10)

                    # Check if the request was successful (status code 200)
                    if response_article.status_code == 200:
                        # Parse the article page content
                        soup_article = BeautifulSoup(response_article.text, 'html.parser')

                        # --- Date-time extraction and filtering ---
                        # Corrected: Target the class name "article__date-published" which is in a <div>
                        date_tag = soup_article.find('div', class_='article__date-published')
                        
                        # --- DEBUG PRINT: Check if date_tag is found ---
                        if date_tag:
                            print(f"  DEBUG: date_tag found for {article_link}. Tag: {date_tag}")
                        else:
                            print(f"  DEBUG: date_tag (div with class 'article__date-published') NOT found for {article_link}.")


                        article_year = None
                        if date_tag:
                            # The text content of this div usually contains the date, e.g., "July 16, 2025 | 12:00am"
                            date_text = date_tag.get_text(strip=True)
                            
                            # --- DEBUG PRINT: Check the extracted date_text ---
                            print(f"  DEBUG: Extracted date_text: '{date_text}' for {article_link}")

                            # Attempt to extract the year, assuming it's part of the text
                            # A simple approach is to look for 4 consecutive digits
                            year_match = re.search(r'\b(202[1-5])\b', date_text)
                            if year_match:
                                article_year = year_match.group(1)

                        # Check if the article year is between 2021 and 2025
                        if article_year and ('2021' <= article_year <= '2025'):
                            # Target the main article content div with class "article__writeup"
                            article_content_div = soup_article.find('div', class_='article__writeup')

                            if article_content_div:
                                # Extract text from all paragraph tags within the identified content div
                                paragraphs = article_content_div.find_all('p')
                                # Filter out empty paragraphs and join the text
                                content_text = ' '.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])

                                # Write the label '1' and the extracted article text to the CSV
                                if content_text: # Only write if there's actual text content
                                    csv_writer.writerow(['1', content_text])
                                    articles_scraped += 1
                                    print(f"Scraped Article {articles_scraped} from {article_year}")

                                    # Check if the desired number of articles has been reached
                                    if articles_scraped >= num_articles_to_scrape:
                                        break # Exit the inner loop
                                else:
                                    print(f"No text content found in paragraphs for article: {article_link}")
                            else:
                                print(f"Could not find 'article__writeup' for: {article_link}. Skipping.")
                        else:
                            # If an article older than 2021 is found,
                            # set the flag to stop further scraping.
                            print(f"Skipping article {article_link}: Published year is not between 2021-2025 (found: {article_year if article_year else 'N/A'}). Stopping further scraping assuming ascending order.")
                            found_older_article = True
                            break # Break out of the 'for' loop (iterating article_link_containers)

                    else:
                        print(f"Failed to retrieve article. Status code: {response_article.status_code} for {article_link}")

            except requests.exceptions.RequestException as req_err:
                print(f"Request error for {article_link}: {req_err}")
            except Exception as e:
                print(f"An error occurred while processing an article link: {e}")

        # If an older article was found during the iteration of the current page's links,
        # break the outer while loop as well.
        if found_older_article:
            break

# Final message after the scraping process completes
print(f"Scraped {articles_scraped} articles. Data saved to {csv_file_path}")
driver.quit() # Close the Selenium browser session