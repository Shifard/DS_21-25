import time
import requests
import csv
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup

base_url = "https://www.gmanetwork.com/news/archives/news-nation/"
num_articles_to_scrape = 80000  
scraped_urls = set()  

driver = webdriver.Chrome()
driver.get(base_url)

# Initialize soup_base with the initial page source before the loop starts
initial_page_source = driver.page_source
soup_base = BeautifulSoup(initial_page_source, 'html.parser')

# Open a CSV file to store the scraped data
csv_file_path = 'gma_nation.csv'
with open(csv_file_path, 'w', encoding='utf-8-sig', newline='') as csv_file:
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(['label', 'article'])  

    articles_scraped = 0
    
    stop_global_scraping = False 

    while articles_scraped < num_articles_to_scrape and not stop_global_scraping:
        print(f"Scraping from the main page... Articles scraped so far: {articles_scraped}")

        # Get the number of articles before the scroll
        initial_article_count = len(soup_base.find_all('li', class_='story left-grid'))

        # Scroll down to the bottom of the page
        driver.find_element("tag name", 'body').send_keys(Keys.END)

        try:
            WebDriverWait(driver, 20).until(
                lambda driver: len(BeautifulSoup(driver.page_source, 'html.parser').find_all('li', class_='story left-grid')) > initial_article_count
            )
        except TimeoutException:
            print("Timeout occurred. No new content was loaded after 20 seconds. Exiting scrolling loop.")
            break
        
        time.sleep(2)  

        updated_page_source = driver.page_source
        soup_base = BeautifulSoup(updated_page_source, 'html.parser')

        list_items = soup_base.find_all('li', class_='story left-grid')
        
        for list_item in list_items:
            if stop_global_scraping:
                break

            try:
                anchor_tag = list_item.find('a', class_='story_link story')
                if anchor_tag: 
                    article_link = anchor_tag['href']
                    
                    if article_link in scraped_urls:
                        continue
                    
                    scraped_urls.add(article_link)
                    
                    print(f"Checking article link: {article_link}")

                    response_article = requests.get(article_link, allow_redirects=True)
                    if response_article.status_code == 200:
                        soup_article = BeautifulSoup(response_article.text, 'html.parser')
                        
                        time_element = soup_article.find('time')
                        if time_element:
                            article_date_text = time_element.get_text()
                            
                            # Check if the date is from 2024 or 2025
                            if '2024' in article_date_text or '2025' in article_date_text:
                                article_content_div = soup_article.find('div', class_='story_main') 
                                
                                if article_content_div:
                                    # Extract the text from all <p> elements
                                    paragraphs = article_content_div.find_all('p')
                                    content_text = ' '.join([p.get_text().strip() for p in paragraphs])
                                    
                                    # Write the scraped data to the CSV file
                                    csv_writer.writerow(['1', content_text])
                                    articles_scraped += 1
                                    print(f"Scraped Article {articles_scraped}: {article_link}")

                                    if articles_scraped >= num_articles_to_scrape:
                                        stop_global_scraping = True 
                                        break 
                                else:
                                    print(f"Skipped article without content: {article_link}")
                            else:
                                print(f"Found an article with date not in 2024/2025: {article_date_text}")
                                print("Stopping the entire scraping process as per instruction.")
                                stop_global_scraping = True 
                                break 
                        else:
                            print(f"Skipped article, no <time> element found: {article_link}")
                    else:
                        print(f"Failed to retrieve article. Status code: {response_article.status_code}")
            except Exception as e:
                print(f"An error occurred while processing an article: {e}")
        
        if stop_global_scraping:
            break

print(f"\nScraping finished. {articles_scraped} articles have been saved to {csv_file_path}")

driver.quit()